"""Local on-demand GlassWire/Control D correlation. No policy or network writes."""

import argparse
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

import controld


class JoinError(RuntimeError):
    pass


def _endpoint(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise JoinError('Expected an explicit Control D endpoint identifier')
    return value


def capture_device(cli, endpoint):
    endpoint = _endpoint(endpoint)
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
    try:
        status = json.loads(subprocess.check_output([str(cli), 'status', '--json'], stderr=subprocess.DEVNULL, **options))
        prefs = json.loads(subprocess.check_output([str(cli), 'debug', 'prefs'], stderr=subprocess.DEVNULL, **options))
        device = status['Self']
        resolver = urlsplit(prefs.get('LocalDNSResolver', ''))
        if (status.get('BackendState') != 'Running' or device.get('OS') != 'windows'
                or not device.get('ID') or not device.get('TailscaleIPs')
                or prefs.get('CorpDNS') is not True or prefs.get('LocalDNSOverride') is not True
                or resolver.scheme != 'https' or resolver.netloc != 'dns.controld.com'
                or resolver.path != '/' + endpoint or resolver.query or resolver.fragment):
            raise JoinError('Windows TailDNS identity and active resolver do not match the selected endpoint')
        return {'source': 'taildns-cli-readonly', 'captured_at_utc': controld.utc_now().isoformat(),
                'node_id': device['ID'], 'os': device['OS'], 'hostname': device.get('HostName'),
                'tailscale_ips': device['TailscaleIPs'],
                'endpoint_binding': {'method': 'active-TailDNS-local-resolver', 'endpoint_id': endpoint}}
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, TypeError, AttributeError):
        raise JoinError('Could not read Windows TailDNS device context') from None


def _answers(raw):
    value = raw.get('answers')
    if not isinstance(value, str):
        raise JoinError('Invalid Control D answer field')
    if not value.strip():
        return set(), False
    # Single IP is documented; semicolon-separated IPs were observed live.
    # Never extract apparent IPs from arbitrary strings/CNAME text.
    try:
        return {str(ipaddress.ip_address(part.strip())) for part in value.split(';')}, False
    except ValueError:
        return set(), True


def correlate(traffic, decisions, context, endpoint, max_age_seconds):
    endpoint = _endpoint(endpoint)
    if type(max_age_seconds) not in (int, float) or not 0 < max_age_seconds < float('inf'):
        raise JoinError('Expected a finite positive analytical correlation age')
    try:
        if (traffic['source'] != 'glasswire-sqlite-observed-v1'
                or traffic['byte_attribution'] != 'application-destination-time-bucket'
                or decisions['source'] != 'controld-activity-csv'
                or context['source'] != 'taildns-cli-readonly' or context['os'] != 'windows'
                or not context['node_id']
                or context['endpoint_binding']['method'] != 'active-TailDNS-local-resolver'
                or context['endpoint_binding']['endpoint_id'] != endpoint
                or decisions.get('endpoint_id', endpoint) != endpoint):
            raise JoinError('Source/device/endpoint binding mismatch')
        if type(traffic['truncated']) is not bool or type(decisions['truncated']) is not bool:
            raise JoinError('Explicit source truncation metadata is required')
        if not isinstance(traffic['rows'], list) or not isinstance(decisions['rows'], list):
            raise JoinError('Expected source record arrays')
        by_ip, unsupported = {}, 0
        for index, decision in enumerate(decisions['rows']):
            if decision['source'] != 'controld-activity-csv':
                raise JoinError('Unexpected DNS-decision source')
            raw = decision['raw']
            stamp = controld._utc(raw['timestamp'])
            if raw['endpointId'] != endpoint:
                continue
            addresses, unknown = _answers(raw)
            unsupported += unknown
            for address in addresses:
                by_ip.setdefault(address, []).append((index, stamp, decision))
        records = []
        for row in traffic['rows']:
            stamp = controld._utc(row['timestamp_utc'])
            if any(type(row[name]) is not int or row[name] < 0 for name in ('inbound_bytes', 'outbound_bytes')):
                raise JoinError('Invalid traffic network-byte counters')
            candidates = []
            address = row['destination_ip']
            usable = bool(address and row['application_path'])
            if usable:
                address = str(ipaddress.ip_address(address))
                for index, dns_stamp, decision in by_ip.get(address, []):
                    age = (stamp - dns_stamp).total_seconds()
                    if 0 <= age <= max_age_seconds:
                        candidates.append({'decision_input_index': index, 'decision': decision,
                                           'age_seconds': age, 'method': 'same-endpoint-answer-ip-preceding-time'})
            match = ('unusable-traffic-identity-or-address' if not usable else
                     'unmatched' if not candidates else 'single-temporal-ip-candidate' if len(candidates) == 1
                     else 'ambiguous-temporal-ip-candidates')
            records.append({'traffic': row, 'dns_candidates': candidates, 'match_status': match})
        return {'source': 'taild-local-joined-v1', 'created_at_utc': controld.utc_now().isoformat(),
                'device_context': context, 'endpoint_id': endpoint, 'max_age_seconds': max_age_seconds,
                'byte_attribution': traffic['byte_attribution'], 'deterministic_domain_attribution': False,
                'traffic_truncated': traffic['truncated'], 'decisions_truncated': decisions['truncated'],
                'query_windows': {'traffic': traffic['query_window'], 'decisions': decisions['query_window']},
                'unsupported_answer_rows': unsupported,
                'uncertainties': ['separate-source-snapshots', 'shared-IPs-and-DNS-reuse',
                                  'dns-cache-and-ttl-not-established', 'not-per-PID-or-socket-bytes',
                                  'endpoint-binding-observed-at-collection-not-historical-proof'],
                'records': records}
    except (KeyError, TypeError, ValueError, AttributeError, controld.ControlDError):
        raise JoinError('Invalid joined-record input') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--traffic-file', required=True)
    parser.add_argument('--decisions-file', required=True)
    parser.add_argument('--tailscale-cli', default='C:/Program Files/Tailscale/tailscale.exe')
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--max-age-seconds', required=True, type=float)
    parser.add_argument('--output', required=True, help='New private JSON outside the repository')
    args = parser.parse_args(argv)
    try:
        traffic = json.loads(Path(args.traffic_file).read_text(encoding='utf-8'))
        decisions = json.loads(Path(args.decisions_file).read_text(encoding='utf-8'))
        context = capture_device(args.tailscale_cli, args.endpoint)
        data = correlate(traffic, decisions, context, args.endpoint, args.max_age_seconds)
        controld.export_private(args.output, data)
        print(json.dumps({'source': data['source'], 'traffic_row_count': len(data['records']),
                          'candidate_row_count': sum(bool(r['dns_candidates']) for r in data['records']),
                          'ambiguous_row_count': sum(len(r['dns_candidates']) > 1 for r in data['records']),
                          'traffic_truncated': data['traffic_truncated'], 'decisions_truncated': data['decisions_truncated']}))
        return 0
    except (OSError, ValueError, JoinError, controld.ControlDError) as error:
        message = str(error) if isinstance(error, (JoinError, controld.ControlDError)) else 'Could not read private source files'
        print(message, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
