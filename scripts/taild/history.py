"""Stage 4 private, on-demand SQLite history. No collector service or network access."""
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess

import controld


class HistoryError(RuntimeError):
    pass


def packed(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(packed(value).encode()).hexdigest()


def instant(value):
    try:
        dt = controld._utc(value)
        delta = dt - datetime(1970, 1, 1, tzinfo=timezone.utc)
        return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    except (controld.ControlDError, TypeError, ValueError, OverflowError):
        raise HistoryError('Expected RFC 3339 UTC timestamp') from None


def utc(value):
    return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=value)).isoformat().replace('+00:00', 'Z')


def bounds(start, end):
    a, b = instant(start), instant(end)
    if a >= b:
        raise HistoryError('Expected ascending half-open UTC bounds')
    return a, b


def _run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, **kwargs).stdout


def private_directory(path):
    """Create only the explicitly selected owned directory; never relax existing ACLs."""
    path = Path(path).absolute()
    repo = Path(__file__).resolve().parents[2]
    if path.resolve().is_relative_to(repo):
        raise HistoryError('History must be outside the repository')
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or getattr(parent, 'is_junction', lambda: False)()):
            raise HistoryError('History cannot use linked directories')
    created = not path.exists()
    try:
        if created:
            path.mkdir(mode=0o700)  # Parent must exist; never claim ownership of a broad tree.
        if os.name == 'nt':
            sid = list(csv.reader(_run(['whoami', '/user', '/fo', 'csv', '/nh']).splitlines()))[0][1]
            allowed = {sid, 'S-1-5-18', 'S-1-5-32-544'}
            if created:
                _run(['icacls', str(path), '/inheritance:r', '/grant:r',
                      f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F'])
            env = {k: v for k, v in os.environ.items() if k.lower() != 'psmodulepath'}
            # pwsh's inherited module path can prevent Windows PowerShell loading
            # its Security module. Let that executable choose its own defaults.
            script = ("$ErrorActionPreference='Stop'; $a=Get-Acl -LiteralPath $env:TAILD_ACL_PATH; "
                      '@{owner=$a.GetOwner([Security.Principal.SecurityIdentifier]).Value; '
                      'allow=@($a.Access | Where-Object AccessControlType -eq Allow | '
                      'ForEach-Object { $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value })} '
                      '| ConvertTo-Json -Compress')
            targets = [path] + [path / name for name in ('history.sqlite3','history.sqlite3-journal','history.sqlite3-wal','history.sqlite3-shm') if (path/name).exists()]
            for target in targets:
                if target.is_symlink() or target.stat().st_nlink > 1:
                    raise HistoryError('History cannot use linked files')
                env['TAILD_ACL_PATH'] = str(target)
                acl = json.loads(_run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], env=env))
                actual = acl['allow']
                # Python 3.13+ mkdir(0700) adds OWNER RIGHTS; that is safe only
                # with this checked owner, never as a broadly trusted principal.
                if acl['owner'] not in allowed or sid not in actual or not set(actual) <= allowed | {'S-1-3-4'}:
                    raise HistoryError('History requires a private owner/SYSTEM/Administrators ACL')
        else:
            targets = [path] + [path/name for name in ('history.sqlite3','history.sqlite3-journal','history.sqlite3-wal','history.sqlite3-shm') if (path/name).exists()]
            for target in targets:
                if target.is_symlink() or target.stat().st_uid != os.getuid() or stat.S_IMODE(target.stat().st_mode) & 0o077:
                    raise HistoryError('History requires owner-only files and directory')
        return path.resolve()
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        raise HistoryError('Cannot establish private history directory') from None


class History:
    def __init__(self, directory, *, now=None, retention_days=None):
        self.directory = private_directory(directory)
        self.path = self.directory / 'history.sqlite3'
        if self.path.exists() and (self.path.is_symlink() or self.path.stat().st_nlink != 1):
            raise HistoryError('History database must be an owned regular file')
        self.now = instant(now or controld.utc_now().isoformat())
        self.db = sqlite3.connect(self.path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.execute('PRAGMA secure_delete=ON')
            self.db.execute('PRAGMA synchronous=FULL')
            if os.name != 'nt':
                os.chmod(self.path, 0o600)
            self._migrate()
            with self.transaction():
                if retention_days is not None:
                    if type(retention_days) is not int or not 1 <= retention_days <= 3650:
                        raise HistoryError('Retention must be 1 to 3650 days')
                    self.db.execute('UPDATE settings SET retention_days=?', (retention_days,))
                self._expire()
        except BaseException:
            self.close()
            raise

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def _migrate(self):
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1, 2, 3):
            raise HistoryError('Unsupported history schema; existing data preserved')
        with self.transaction():
            if version == 0:
                statements = [
                    'CREATE TABLE settings(retention_days INTEGER NOT NULL,expiry_floor INTEGER NOT NULL)',
                    'INSERT INTO settings VALUES(7,0)',
                    'CREATE TABLE sources(id TEXT PRIMARY KEY,kind TEXT NOT NULL,metadata TEXT NOT NULL)',
                    'CREATE TABLE runs(revision INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT NOT NULL REFERENCES sources(id),start INTEGER NOT NULL,end INTEGER NOT NULL,state TEXT NOT NULL,collected INTEGER NOT NULL,metadata TEXT NOT NULL)',
                    'CREATE TABLE checkpoints(source TEXT PRIMARY KEY REFERENCES sources(id),start INTEGER NOT NULL,complete_through INTEGER NOT NULL,revision INTEGER NOT NULL)',
                    'CREATE TABLE applications(id TEXT PRIMARY KEY,path TEXT,blob_sha256 TEXT)',
                    'CREATE TABLE traffic(source TEXT NOT NULL REFERENCES sources(id),identity TEXT NOT NULL,time INTEGER NOT NULL,application TEXT REFERENCES applications(id),destination TEXT,port INTEGER NOT NULL,inbound INTEGER NOT NULL,outbound INTEGER NOT NULL,revision INTEGER NOT NULL,data TEXT NOT NULL,PRIMARY KEY(source,identity))',
                    'CREATE TABLE dns(source TEXT NOT NULL REFERENCES sources(id),identity TEXT NOT NULL,ordinal INTEGER NOT NULL,time INTEGER NOT NULL,endpoint TEXT NOT NULL,question TEXT NOT NULL,revision INTEGER NOT NULL,data TEXT NOT NULL,PRIMARY KEY(source,identity,ordinal))',
                    'CREATE INDEX traffic_time ON traffic(time)',
                    'CREATE INDEX dns_time ON dns(time)']
                for sql in statements:
                    self.db.execute(sql)
                self.db.execute('PRAGMA user_version=1')
            if version < 2:
                self.db.execute('CREATE TABLE suppressions(kind TEXT NOT NULL,source TEXT,start INTEGER NOT NULL,end INTEGER NOT NULL,application_hash TEXT)')
                self.db.execute('PRAGMA user_version=2')
            if version < 3:
                self.db.execute('ALTER TABLE settings ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')
                self.db.execute('UPDATE settings SET revision=(SELECT coalesce(max(revision),0) FROM runs)')
                self.db.execute('PRAGMA user_version=3')

    def _bump(self):
        self.db.execute('UPDATE settings SET revision=revision+1')
        return self.db.execute('SELECT revision FROM settings').fetchone()[0]

    def _expire(self):
        days, floor = self.db.execute('SELECT retention_days,expiry_floor FROM settings').fetchone()
        floor = max(floor, self.now - days * 86400 * 1000000)
        if floor != self.db.execute('SELECT expiry_floor FROM settings').fetchone()[0]:
            self._bump()
        self.db.execute('UPDATE settings SET expiry_floor=?', (floor,))
        for table in ('traffic', 'dns'):
            self.db.execute(f'DELETE FROM {table} WHERE time<?', (floor,))
        self.db.execute('DELETE FROM runs WHERE end<=?', (floor,))
        self.db.execute('UPDATE runs SET start=? WHERE start<?', (floor, floor))
        self.db.execute('DELETE FROM suppressions WHERE end<=?', (floor,))
        self._orphan_apps()
        return floor

    def _orphan_apps(self):
        self.db.execute('DELETE FROM applications WHERE id NOT IN (SELECT application FROM traffic WHERE application IS NOT NULL)')

    def cleanup(self):
        with self.transaction():
            self._expire()
        return self.health()

    def _source(self, kind, scope, generation=None, endpoint=None):
        if not isinstance(scope, str) or not scope.strip():
            raise HistoryError('Explicit host/account scope is required')
        key = digest([kind, scope, generation, endpoint])
        metadata = packed({'scope': scope, 'generation': generation, 'endpoint': endpoint})
        self.db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?)', (key, kind, metadata))
        return key

    def _run(self, source, a, b, data, state):
        collected = instant(data['collected_at_utc'])
        metadata = {k: v for k, v in data.items() if k != 'rows'}
        revision = self._bump()
        self.db.execute('INSERT INTO runs(revision,source,start,end,state,collected,metadata) VALUES(?,?,?,?,?,?,?)',
                        (revision,source, a, b, state, collected, packed(metadata)))
        return revision

    def _checkpoint(self, source, revision):
        spans = self.db.execute("SELECT start,end FROM runs WHERE source=? AND state='complete' ORDER BY start,end", (source,)).fetchall()
        if not spans:
            return
        start, through = spans[0]
        for a, b in spans[1:]:
            if a > through:
                break
            through = max(through, b)
        self.db.execute('INSERT INTO checkpoints VALUES(?,?,?,?) ON CONFLICT(source) DO UPDATE SET start=excluded.start,complete_through=excluded.complete_through,revision=excluded.revision',
                        (source, start, through, revision))

    def _suppressed(self, kind, source, time, application=None):
        return self.db.execute('SELECT 1 FROM suppressions WHERE kind=? AND (source IS NULL OR source=?) AND start<=? AND end>? AND (application_hash IS NULL OR application_hash=?) LIMIT 1',
                               (kind, source, time, time, digest(application) if application is not None else None)).fetchone() is not None

    def import_traffic(self, data, scope):
        a, b = bounds(data['query_window']['start_inclusive'], data['query_window']['end_exclusive'])
        generation = data.get('generation')
        if not generation:
            raise HistoryError('Traffic requires physical database generation provenance')
        rows = []
        for row in data['rows']:
            time = instant(row['timestamp_utc'])
            if not a <= time < b or time != row['timestamp_raw'] * 1000000:
                raise HistoryError('Traffic row is outside its declared interval')
            for field in ('inbound_bytes', 'outbound_bytes'):
                if type(row[field]) is not int or not 0 <= row[field] <= 2**63-1:
                    raise HistoryError('Invalid exact traffic counter')
            p = row['provenance']
            identity = digest([p['rowid'], row['timestamp_raw'], row['application_id'],
                               p['remote_host_blob_sha256'],
                               row['destination_port'], row['protocol_raw'], row['flags_raw']])
            rows.append((row, time, identity))
        with self.transaction():
            floor = self._expire()
            source = self._source('traffic', scope, generation)
            state = 'truncated' if data['truncated'] else 'complete'
            revision = self._run(source, a, b, data, state)
            for row, time, identity in rows:
                if time < floor or self._suppressed('traffic', source, time, row['application_path']):
                    continue
                app = digest([generation.get('application_database'), row['application_id'], row['provenance']['application_blob_sha256']])
                self.db.execute('INSERT OR IGNORE INTO applications VALUES(?,?,?)', (app, row['application_path'], row['provenance']['application_blob_sha256']))
                self.db.execute('INSERT INTO traffic VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source,identity) DO UPDATE SET application=excluded.application,inbound=excluded.inbound,outbound=excluded.outbound,revision=excluded.revision,data=excluded.data',
                                (source, identity, time, app, row['destination_ip'], row['destination_port'], row['inbound_bytes'], row['outbound_bytes'], revision, packed(row)))
            self._checkpoint(source, revision)
            self._expire()
        return {'revision': revision, 'state': state, 'source': source}

    def import_dns(self, data, scope, endpoint):
        if not isinstance(endpoint, str) or not endpoint:
            raise HistoryError('Explicit Control D endpoint scope is required')
        if data.get('endpoint_id') != endpoint:
            raise HistoryError('Control D slice endpoint scope does not match')
        window = data['query_window']
        a, b = bounds(window['start_inclusive'], window.get('end_exclusive') or window['end_inclusive'])
        occurrences, rows = Counter(), []
        for row in data['rows']:
            raw = row['raw']
            time = instant(raw['timestamp'])
            if raw['endpointId'] != endpoint:
                raise HistoryError('Control D row endpoint scope does not match')
            # Provider upper bound may be inclusive. Local ownership is always [a,b).
            if time == b:
                continue
            if not a <= time < b:
                raise HistoryError('Control D row is outside its declared interval')
            key = digest(raw)
            occurrences[key] += 1
            rows.append((row, time, key, occurrences[key]))
        with self.transaction():
            floor = self._expire()
            source = self._source('dns', scope, endpoint=endpoint)
            state = 'truncated' if data['truncated'] else 'complete'
            revision = self._run(source, a, b, data, state)
            # A partial multiset cannot safely retract or replace an earlier complete one.
            if state == 'complete':
                self.db.execute('DELETE FROM dns WHERE source=? AND time>=? AND time<?', (source, a, b))
                for row, time, key, ordinal in rows:
                    if time < floor or self._suppressed('dns', source, time):
                        continue
                    self.db.execute('INSERT INTO dns VALUES(?,?,?,?,?,?,?,?)',
                                    (source, key, ordinal, time, endpoint, row['raw']['question'], revision, packed(row)))
            self._checkpoint(source, revision)
            self._expire()
        return {'revision': revision, 'state': state, 'source': source}

    def record_gap(self, kind, scope, start, end, reason, *, generation=None, endpoint=None):
        if kind not in ('traffic', 'dns') or reason not in ('source-expired', 'read-failed', 'irreducibly-capped'):
            raise HistoryError('Unsupported source gap')
        a, b = bounds(start, end)
        with self.transaction():
            source = self._source(kind, scope, generation, endpoint)
            revision = self._run(source, a, b, {'collected_at_utc': utc(self.now), 'reason': reason}, reason)
        return {'revision': revision, 'source': source, 'state': reason}

    def delete(self, kind, start, end, *, source=None, application_path=None):
        if kind not in ('traffic', 'dns') or (kind == 'dns' and application_path is not None):
            raise HistoryError('Unsupported deletion scope')
        a, b = bounds(start, end)
        with self.transaction():
            self._bump()
            self.db.execute('INSERT INTO suppressions VALUES(?,?,?,?,?)',
                            (kind, source, a, b, digest(application_path) if application_path is not None else None))
            filters = {'source': source}
            if application_path is not None:
                filters['application_path'] = application_path
            clause, params = self._where(kind, a, b, filters)
            self.db.execute(f'DELETE FROM {kind} WHERE rowid IN (SELECT f.rowid FROM {kind} f LEFT JOIN applications app ON ' +
                            ('app.id=f.application' if kind == 'traffic' else '0') + ' WHERE ' + clause + ')', params)
            self._orphan_apps()

    def _where(self, kind, a, b, filters):
        mapping = {'source': 'f.source'}
        mapping |= ({'application_path': 'app.path', 'destination_ip': 'f.destination', 'destination_port': 'f.port'}
                    if kind == 'traffic' else {'endpoint': 'f.endpoint', 'question': 'f.question'})
        if set(filters) - mapping.keys():
            raise HistoryError('Unsupported local fact filter')
        clause, params = ['f.time>=?', 'f.time<?'], [a, b]
        for key, value in filters.items():
            if value is not None:
                clause.append(mapping[key] + '=?')
                params.append(value)
        return ' AND '.join(clause), params

    def query(self, kind, start, end, *, limit=1000, **filters):
        if kind not in ('traffic', 'dns') or type(limit) is not int or not 1 <= limit <= 10000:
            raise HistoryError('Expected traffic/dns facts and a bounded row limit')
        a, b = bounds(start, end)
        clause, params = self._where(kind, a, b, filters)
        self.db.execute('BEGIN')
        try:
            revision = self.db.execute('SELECT revision FROM settings').fetchone()[0]
            rows, count, incoming, outgoing = [], 0, 0, 0
            join = ' LEFT JOIN applications app ON app.id=f.application' if kind == 'traffic' else ''
            for row in self.db.execute(f'SELECT f.* FROM {kind} f{join} WHERE {clause} ORDER BY f.time,f.source,f.identity' + (',f.ordinal' if kind == 'dns' else ''), params):
                count += 1
                if kind == 'traffic':
                    incoming += row['inbound']
                    outgoing += row['outbound']
                if len(rows) < limit:
                    rows.append({'source_id': row['source'], 'fact': json.loads(row['data'])})
            coverage = self._coverage(kind, a, b, filters.get('source'),filters.get('endpoint'))
            return {'revision': revision, 'kind': kind, 'row_count': count, 'rows': rows,
                    'truncated': count > limit, 'inbound_bytes': incoming, 'outbound_bytes': outgoing,
                    'coverage': coverage}
        finally:
            self.db.execute('ROLLBACK')

    def _coverage(self, kind, a, b, selected=None, endpoint=None):
        sql='SELECT DISTINCT s.id,s.metadata FROM sources s JOIN runs r ON r.source=s.id WHERE s.kind=? AND r.end>? AND r.start<?'
        params=[kind,a,b]
        if selected:
            sql+=' AND s.id=?'
            params.append(selected)
        sources=[r[0] for r in self.db.execute(sql,params)
                 if endpoint is None or json.loads(r[1]).get('endpoint')==endpoint]
        floor = self.db.execute('SELECT expiry_floor FROM settings').fetchone()[0]
        detail = []
        for source in sources:
            cursor, gaps = max(a, floor), []
            if a < floor:
                gaps.append({'start': utc(a), 'end': utc(min(b, floor)), 'reason': 'retention-expired'})
            for x, y in self.db.execute("SELECT start,end FROM runs WHERE source=? AND state='complete' AND end>? AND start<? ORDER BY start,end", (source, a, b)):
                x, y = max(a, floor, x), min(b, y)
                if x > cursor:
                    gaps.append({'start': utc(cursor), 'end': utc(x), 'reason': 'unobserved'})
                cursor = max(cursor, y)
            if cursor < b:
                gaps.append({'start': utc(cursor), 'end': utc(b), 'reason': 'unobserved'})
            attempts = []
            for x, y, state, revision in self.db.execute("SELECT start,end,state,revision FROM runs WHERE source=? AND end>? AND start<? AND state!='complete' ORDER BY revision", (source, a, b)):
                through = max(x, a, floor)
                stop = min(y, b)
                for ca, cb in self.db.execute("SELECT start,end FROM runs WHERE source=? AND state='complete' AND revision>? AND end>? AND start<? ORDER BY start,end", (source, revision, through, stop)):
                    if ca > through:
                        break
                    through = max(through, cb)
                attempts.append({'start': utc(x), 'end': utc(y), 'state': state, 'resolved': through >= stop})
            deleted = self.db.execute('SELECT count(*) FROM suppressions WHERE kind=? AND (source IS NULL OR source=?) AND end>? AND start<?', (kind, source, a, b)).fetchone()[0]
            detail.append({'source': source, 'gaps': gaps, 'incomplete_attempts': attempts, 'deletion_scopes': deleted})
        return {'incomplete': not sources or any(r['gaps'] or any(not attempt['resolved'] for attempt in r['incomplete_attempts']) or r['deletion_scopes'] for r in detail),
                'sources': detail, 'snapshot_limit': 'separate source transactions; late corrections remain possible'}

    def health(self):
        days, floor = self.db.execute('SELECT retention_days,expiry_floor FROM settings').fetchone()
        sources = []
        for row in self.db.execute('SELECT s.id,s.kind,c.complete_through,c.revision FROM sources s LEFT JOIN checkpoints c ON c.source=s.id ORDER BY s.id'):
            sources.append({'id': row[0], 'kind': row[1], 'complete_through': utc(row[2]) if row[2] is not None else None, 'reconciliation_revision': row[3]})
        return {'schema_version': self.db.execute('PRAGMA user_version').fetchone()[0],
                'retention_days': days, 'expiry_floor': utc(floor), 'storage_bytes': self.path.stat().st_size,
                'protection': 'OS ACL only; plaintext SQLite; disk protection remains OS responsibility',
                'sources': sources}
