"""Read-only Control D capability slice. No policy writes or background collection."""

import argparse
import calendar
import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

API_BASE = 'https://api.controld.com'
REPO_ROOT = Path(__file__).resolve().parents[2]


class ControlDError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        # Never forward a bearer token to a redirect destination, even same-host.
        return None


def utc_now():
    return datetime.now(timezone.utc)


def _header(value):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ControlDError('Invalid credential or organization header')
    return value.strip()


def _read(url, token, organization=None):
    headers = {'Authorization': 'Bearer ' + _header(token), 'User-Agent': 'TailD-readonly-development'}
    if organization is not None:
        headers['X-Force-Org-Id'] = _header(organization)
    try:
        return build_opener(NoRedirect).open(Request(url, headers=headers, method='GET'))
    except HTTPError as error:
        status = error.code
        error.close()
        raise ControlDError(f'Control D read rejected (HTTP {status})') from None
    except (URLError, OSError):
        raise ControlDError('Control D network read failed') from None


def _body(path, token, organization=None):
    with _read(API_BASE + path, token, organization) as response:
        try:
            envelope = json.load(response)
        except (ValueError, OSError):
            raise ControlDError('Invalid Control D JSON response') from None
    if not isinstance(envelope, dict) or envelope.get('success') is not True:
        raise ControlDError('Control D returned an unsuccessful read')
    if not isinstance(envelope.get('body'), dict):
        raise ControlDError('Invalid Control D JSON envelope')
    return envelope['body']


def inventory(token, organization=None):
    result = {'source': 'controld-api'}
    for controller in ('devices', 'profiles'):
        records = _body('/' + controller, token, organization).get(controller)
        if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
            raise ControlDError('Invalid Control D inventory envelope')
        result[controller] = records
    return result


def _instance(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', value):
        raise ControlDError('Expected a single Control D analytics instance label')
    return value


def analytics_instance(token, organization=None):
    account = _body('/users', token, organization)
    org = account.get('org')
    region = org.get('stats_endpoint') if isinstance(org, dict) else account.get('stats_endpoint')
    return _instance(region)


def _utc(value):
    try:
        if 'T' not in value:
            raise ValueError()
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError()
        return parsed
    except (ValueError, TypeError):
        raise ControlDError('Expected an RFC 3339 UTC timestamp') from None


def activity(token, account_type, instance, start, end=None, endpoint=None,
             organization=None, limit=1):
    if account_type not in ('personal', 'organization'):
        raise ControlDError('Expected personal or organization account type')
    instance = _instance(instance) if instance is not None else analytics_instance(token, organization)
    if limit < 1:
        raise ControlDError('Decision limit must be positive')
    since = _utc(start)
    now = utc_now()
    last_month = now.month - 1 or 12
    last_year = now.year - (now.month == 1)
    earliest = now.replace(year=last_year, month=last_month,
                           day=min(now.day, calendar.monthrange(last_year, last_month)[1]))
    if since < earliest or since > now:
        raise ControlDError('Control D CSV start must be within the past calendar month')
    query = {'startTime': start}
    if end is not None:
        until = _utc(end)
        if until < since or until > now:
            raise ControlDError('Control D CSV end must follow start and not be in the future')
        query['endTime'] = end
    if endpoint is not None:
        query['endpointId'] = endpoint
    url = 'https://' + instance + '.analytics.controld.com/v2/activity-log/csv?' + urlencode(query)
    result = []
    with _read(url, token, organization) as response:
        try:
            reader = csv.DictReader(io.TextIOWrapper(response, encoding='utf-8-sig', newline=''))
            required = {'timestamp', 'endpointId', 'question', 'action'}
            if not required.issubset(reader.fieldnames or []):
                raise ControlDError('Invalid Control D decision CSV columns')
            for row in reader:
                if None in row or any(row[column] is None for column in required):
                    raise ControlDError('Invalid Control D decision CSV row')
                _utc(row['timestamp'])
                result.append({'source': 'controld-activity-csv', 'raw': row})
                if len(result) == limit:
                    break
        except (csv.Error, UnicodeError, OSError):
            raise ControlDError('Invalid Control D decision CSV stream') from None
    return result


def export_private(path, data):
    output = Path(path).resolve()
    if output.is_relative_to(REPO_ROOT):
        raise ControlDError('Private exports must be outside the repository')
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except OSError:
        raise ControlDError('Private export could not be created; existing files are never overwritten') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token-stdin', action='store_true', help='Read token from one stdin line; never echoed')
    parser.add_argument('--organization', help='Optional sub-organization scope')
    parser.add_argument('--output', help='Optional private JSON file outside this repo; never overwritten')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('inventory', help='Read device/profile inventory')
    log = commands.add_parser('activity', help='Read a small authenticated activity CSV slice')
    log.add_argument('--account-type', choices=['personal', 'organization'], required=True)
    log.add_argument('--instance', help='Optional explicit label; otherwise discover from account metadata')
    log.add_argument('--start', required=True)
    log.add_argument('--end')
    log.add_argument('--endpoint')
    log.add_argument('--limit', type=int, default=1)
    args = parser.parse_args(argv)
    try:
        token = (sys.stdin.readline().rstrip('\r\n') if args.token_stdin
                 else os.environ.get('CONTROLD_READ_TOKEN', ''))
        if args.command == 'inventory':
            data = inventory(token, args.organization)
            summary = {'source': data['source'], 'device_count': len(data['devices']),
                       'profile_count': len(data['profiles'])}
        else:
            data = activity(token, args.account_type, args.instance, args.start, args.end,
                            args.endpoint, args.organization, args.limit)
            summary = {'source': 'controld-activity-csv', 'decision_count': len(data)}
        if args.output:
            export_private(args.output, data)
        print(json.dumps(summary))
        return 0
    except ControlDError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
