"""On-demand reader for the observed GlassWire SQLite layout. No service or writes."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import ipaddress
import math
import ntpath
from pathlib import Path
import re
import sqlite3
import sys
import json

import controld


class GlassWireError(RuntimeError):
    pass


def _varint(blob, offset):
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(blob):
            raise GlassWireError('Truncated GlassWire binary record')
        byte = blob[offset]
        offset += 1
        if shift == 63 and byte > 1:
            break
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise GlassWireError('Invalid GlassWire binary integer')


def _fields(blob):
    if not isinstance(blob, bytes):
        raise GlassWireError('Expected GlassWire binary record')
    fields = {}
    offset = 0
    while offset < len(blob):
        tag, offset = _varint(blob, offset)
        number, wire = tag >> 3, tag & 7
        if not 1 <= number < 1 << 29:
            raise GlassWireError('Invalid GlassWire binary field')
        if wire == 0:
            value, offset = _varint(blob, offset)
        elif wire in (1, 2, 5):
            if wire == 2:
                size, offset = _varint(blob, offset)
            else:
                size = 8 if wire == 1 else 4
            if size > len(blob) - offset:
                raise GlassWireError('Truncated GlassWire binary field')
            value = blob[offset:offset + size]
            offset += size
        else:
            raise GlassWireError('Unsupported GlassWire binary wire type')
        fields.setdefault(number, []).append((wire, value))
    return fields


def _single(fields, number, wire):
    values = fields.get(number, [])
    if len(values) != 1 or values[0][0] != wire:
        raise GlassWireError('Missing or ambiguous GlassWire binary field')
    return values[0][1]


def decode_address(blob):
    fields = _fields(blob)
    family = _single(fields, 1, 0)
    if family != 1:
        return None, 'unsupported-address-family'
    value = _single(fields, 2, 0)
    if value > 0xffffffff:
        raise GlassWireError('Invalid GlassWire IPv4 field')
    return str(ipaddress.ip_address(value.to_bytes(4, 'little'))), 'observed-ipv4-encoding'


def decode_application(blob):
    fields = _fields(blob)
    if 6 not in fields:
        return None, 'unsupported-application-path'
    try:
        path = _single(fields, 6, 2).decode('utf-8')
    except UnicodeError:
        raise GlassWireError('Invalid GlassWire application encoding') from None
    if '\x00' in path or not ntpath.isabs(path) or not path.strip():
        raise GlassWireError('Invalid GlassWire application path')
    return path, 'observed-executable-path-field'


def _connect(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        return connection
    except Exception:
        connection.close()
        raise


def _schema(connection, table, required):
    # Table names are internal constants, never user input.
    columns = {row[1]: row[2].upper() for row in connection.execute('PRAGMA table_info(' + table + ')')}
    if any(columns.get(name) != kind for name, kind in required.items()):
        raise GlassWireError('Unsupported GlassWire database schema')


def read_traffic(stats_db, main_db, start, end, limit=1000):
    try:
        since, until = controld._utc(start), controld._utc(end)
    except controld.ControlDError:
        raise GlassWireError('Expected GlassWire RFC 3339 UTC query bounds') from None
    if since >= until or isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise GlassWireError('Expected ascending query bounds and positive row limit')
    stats_db, main_db = Path(stats_db).resolve(), Path(main_db).resolve()
    if not re.fullmatch(r'glasswire_stats_1sec_[0-9]+\.db', stats_db.name):
        raise GlassWireError('Select one observed one-second GlassWire statistics database')
    rows, applications = [], {}
    try:
        with closing(_connect(stats_db)) as stats, closing(_connect(main_db)) as apps:
            _schema(stats, 'traffic_stats', {name: 'INTEGER' for name in (
                'timestamp', 'app_id', 'remote_port', 'protocol', 'flags',
                'inbound_bytes', 'outbound_bytes', 'threat_level')} | {'remote_host': 'BLOB'})
            _schema(apps, 'applications', {'id': 'INTEGER', 'data': 'BLOB'})
            raw_rows = stats.execute(
                'SELECT rowid,timestamp,app_id,remote_host,remote_port,protocol,flags,inbound_bytes,outbound_bytes,threat_level '
                'FROM traffic_stats WHERE timestamp>=? AND timestamp<? ORDER BY timestamp,rowid LIMIT ?',
                (math.ceil(since.timestamp()), math.ceil(until.timestamp()), limit + 1)).fetchall()
            for raw in raw_rows[:limit]:
                rowid, timestamp, app_id, address, port, protocol, flags, incoming, outgoing, threat = raw
                if (any(type(value) is not int for value in (rowid, timestamp, app_id, port, protocol, flags, incoming, outgoing))
                        or (threat is not None and type(threat) is not int)):
                    raise GlassWireError('Invalid GlassWire integer columns')
                if not 0 <= port <= 65535 or min(incoming, outgoing) < 0:
                    raise GlassWireError('Invalid GlassWire port or network-byte counter')
                destination, address_status = decode_address(address)
                if app_id not in applications:
                    record = apps.execute('SELECT data FROM applications WHERE id=?', (app_id,)).fetchone()
                    if record is None:
                        applications[app_id] = (None, 'missing-application-record', None)
                    else:
                        path, status = decode_application(record[0])
                        applications[app_id] = (path, status, hashlib.sha256(record[0]).hexdigest())
                path, status, digest = applications[app_id]
                rows.append({'timestamp_utc': datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                             'timestamp_raw': timestamp, 'application_id': app_id,
                             'application_path': path, 'application_status': status,
                             'destination_ip': destination, 'destination_status': address_status,
                             'destination_port': port, 'inbound_bytes': incoming, 'outbound_bytes': outgoing,
                             'protocol_raw': protocol, 'flags_raw': flags, 'threat_level_raw': threat,
                             'provenance': {'database': str(stats_db), 'table': 'traffic_stats', 'rowid': rowid,
                                            'application_database': str(main_db), 'application_table': 'applications',
                                            'application_blob_sha256': digest,
                                            'remote_host_blob_sha256': hashlib.sha256(address).hexdigest()}})
    except (sqlite3.Error, OSError, OverflowError, ValueError):
        raise GlassWireError('GlassWire read failed; verify read access and source compatibility') from None
    return {'source': 'glasswire-sqlite-observed-v1', 'collected_at_utc': controld.utc_now().isoformat(),
            'query_window': {'start_inclusive': start, 'end_exclusive': end},
            'selected_scale_from_filename_seconds': 1,
            'byte_attribution': 'application-destination-time-bucket',
            'consistency': 'separate-read-transactions-including-wal',
            'truncated': len(raw_rows) > limit, 'rows': rows,
            'unsupported_address_rows': sum(row['destination_ip'] is None for row in rows)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stats-db', required=True)
    parser.add_argument('--main-db', default='C:/ProgramData/GlassWire/service-full/glasswire.db')
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--output', help='New private JSON outside the repository; never overwritten')
    args = parser.parse_args(argv)
    try:
        data = read_traffic(args.stats_db, args.main_db, args.start, args.end, args.limit)
        if args.output:
            controld.export_private(args.output, data)
        print(json.dumps({'source': data['source'], 'row_count': len(data['rows']),
                          'truncated': data['truncated'], 'unsupported_address_rows': data['unsupported_address_rows']}))
        return 0
    except (GlassWireError, controld.ControlDError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
