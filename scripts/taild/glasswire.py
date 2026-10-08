"""On-demand reader for the observed GlassWire SQLite layout. No service or writes."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import ipaddress
import math
import ntpath
import os
from pathlib import Path
import re
import sqlite3
import sys
import json

import controld


class GlassWireError(RuntimeError):
    pass


def physical_identity(path):
    path = Path(path).resolve(strict=True)
    info = path.stat()
    if not info.st_ino:
        raise GlassWireError('Source has no stable filesystem identity')
    # A renamed/hard-linked filename is not a new physical generation. Paths
    # belong to row provenance, not to the generation's identity.
    return {'device': info.st_dev, 'file_id': str(info.st_ino),
            'birth_ns': getattr(info, 'st_birthtime_ns', None)}


def discover(directory=None):
    """Use the observed catalog; never glob scales or follow catalog path escapes."""
    version = 'explicit-override-version-unverified'
    if directory is None:
        if os.name != 'nt':
            raise GlassWireError('Explicit GlassWire data directory required on this platform')
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Services\GlassWire') as key:
                binary = winreg.QueryValueEx(key, 'ImagePath')[0].strip('"')
            if Path(binary).name.lower() != 'gwctlsrv.exe' or not Path(binary).is_file():
                raise GlassWireError('Unrecognized installed GlassWire service')
            # Installation identity is verified first; the default observed data
            # directory is accepted only if its read-only catalog also validates.
            directory = Path(os.environ['ProgramData']) / 'GlassWire' / 'service-full'
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall') as uninstall:
                for i in range(winreg.QueryInfoKey(uninstall)[0]):
                    with winreg.OpenKey(uninstall, winreg.EnumKey(uninstall, i)) as entry:
                        try:
                            if winreg.QueryValueEx(entry, 'DisplayName')[0].startswith('GlassWire '):
                                version = winreg.QueryValueEx(entry, 'DisplayVersion')[0]
                        except FileNotFoundError:
                            continue
        except (OSError, KeyError):
            raise GlassWireError('Cannot verify installed GlassWire metadata') from None
    root = Path(directory).resolve(strict=True)
    main = root / 'glasswire.db'
    try:
        with closing(_connect(main)) as db:
            _schema(db, 'stats_databases', {'filename': 'BLOB', 'timestamp': 'INTEGER', 'expire_time': 'INTEGER', 'scale': 'INTEGER'})
            entries = list(db.execute('SELECT filename,timestamp,expire_time,scale FROM stats_databases ORDER BY timestamp,filename'))
        databases = []
        for encoded, timestamp, expires, scale in entries:
            if not isinstance(encoded, bytes):
                raise GlassWireError('Unsupported GlassWire catalog filename')
            try:
                filename = encoded.decode('utf-8')
            except UnicodeError:
                raise GlassWireError('Invalid GlassWire catalog filename encoding') from None
            if '\x00' in filename or ntpath.basename(filename) != filename or Path(filename).name != filename:
                raise GlassWireError('GlassWire catalog filename must be a leaf name')
            path = (root / 'stats' / filename).resolve()
            if not path.is_relative_to(root):
                raise GlassWireError('GlassWire catalog path leaves approved directory')
            if not re.fullmatch(r'glasswire_stats_1sec_[0-9]+\.db', path.name):
                continue
            if scale != 1 or type(timestamp) is not int or type(expires) is not int:
                raise GlassWireError('Incompatible GlassWire one-second catalog record')
            databases.append({'path': str(path), 'timestamp': timestamp, 'expire_time': expires,
                              'filename_blob_sha256': hashlib.sha256(encoded).hexdigest(),
                              'present': path.is_file()})
        return {'directory': str(root), 'main_database': str(main), 'version': version, 'databases': databases}
    except (sqlite3.Error, OSError):
        raise GlassWireError('GlassWire catalog read failed') from None


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
    if family == 2:
        packed = _single(fields, 3, 2)
        if len(packed) != 16:
            raise GlassWireError('Invalid GlassWire IPv6 field')
        return str(ipaddress.IPv6Address(packed)), 'observed-ipv6-network-order'
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
        generation = {'traffic_database': physical_identity(stats_db),
                      'application_database': physical_identity(main_db)}
        with closing(_connect(stats_db)) as stats, closing(_connect(main_db)) as apps:
            _schema(stats, 'traffic_stats', {name: 'INTEGER' for name in (
                'timestamp', 'app_id', 'remote_port', 'protocol', 'flags',
                'inbound_bytes', 'outbound_bytes', 'threat_level')} | {'remote_host': 'BLOB'})
            _schema(apps, 'applications', {'id': 'INTEGER', 'data': 'BLOB'})
            schema = list(stats.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"))
            schema_sha = hashlib.sha256(json.dumps(schema).encode()).hexdigest()
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
                                            'remote_host_blob_sha256': hashlib.sha256(address).hexdigest(),
                                            'raw_row_sha256': hashlib.sha256(json.dumps([v.hex() if isinstance(v,bytes) else v for v in raw]).encode()).hexdigest()}})
        if generation != {'traffic_database': physical_identity(stats_db), 'application_database': physical_identity(main_db)}:
            raise GlassWireError('GlassWire source replaced during read; slice discarded')
    except (sqlite3.Error, OSError, OverflowError, ValueError):
        raise GlassWireError('GlassWire read failed; verify read access and source compatibility') from None
    return {'source': 'glasswire-sqlite-observed-v1', 'collected_at_utc': controld.utc_now().isoformat(),
            'generation': generation, 'schema_sha256': schema_sha,
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
