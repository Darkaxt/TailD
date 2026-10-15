"""Private on-demand SQLite facts and observed snapshots. No service or network access."""
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
import package_sqlite


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


def _windows_private_object(path, sid, *, optional=False):
    """Inspect one opened object, including a journal unlinked after open."""
    import pywintypes
    import win32con
    import win32file
    import win32security
    try:
        handle=win32file.CreateFile(str(path),win32con.READ_CONTROL|0x80, # FILE_READ_ATTRIBUTES
            win32con.FILE_SHARE_READ|win32con.FILE_SHARE_WRITE|win32con.FILE_SHARE_DELETE,
            None,win32con.OPEN_EXISTING,
            win32con.FILE_FLAG_BACKUP_SEMANTICS|win32file.FILE_FLAG_OPEN_REPARSE_POINT,None)
    except pywintypes.error as error:
        if optional and error.winerror==2:return
        raise HistoryError('Cannot inspect private history object') from None
    try:
        info=win32file.GetFileInformationByHandle(handle)
        if info[0]&win32con.FILE_ATTRIBUTE_REPARSE_POINT or (
                not info[0]&win32con.FILE_ATTRIBUTE_DIRECTORY and info[7]>1):
            raise HistoryError('History cannot use linked files')
        descriptor=win32security.GetSecurityInfo(handle,win32security.SE_FILE_OBJECT,
            win32security.OWNER_SECURITY_INFORMATION|win32security.DACL_SECURITY_INFORMATION)
        owner=win32security.ConvertSidToStringSid(descriptor.GetSecurityDescriptorOwner())
        dacl=descriptor.GetSecurityDescriptorDacl()
        if dacl is None:raise HistoryError('History requires a private ACL')
        allowed={sid,'S-1-5-18','S-1-5-32-544'}
        actual=set()
        for index in range(dacl.GetAceCount()):
            ace=dacl.GetAce(index)
            if ace[0][0] in (win32security.ACCESS_ALLOWED_ACE_TYPE,win32security.ACCESS_ALLOWED_OBJECT_ACE_TYPE):
                actual.add(win32security.ConvertSidToStringSid(ace[-1]))
            elif ace[0][0] not in (win32security.ACCESS_DENIED_ACE_TYPE,win32security.ACCESS_DENIED_OBJECT_ACE_TYPE):
                raise HistoryError('Unsupported history ACL')
        if owner not in allowed or sid not in actual or not actual<=allowed|{'S-1-3-4'}:
            raise HistoryError('History requires a private owner/SYSTEM/Administrators ACL')
    except pywintypes.error:
        raise HistoryError('Cannot inspect private history object') from None
    finally:
        handle.Close()


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
            import reader
            sid = reader.current_sid()
            if created:
                _run(['icacls', str(path), '/inheritance:r', '/grant:r',
                      f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F'])
            private_names = ('history.sqlite3','history.sqlite3-journal','history.sqlite3-wal','history.sqlite3-shm',
                'runtime.json','runtime.pending.json','runtime-status.json','runtime-status.pending.json',
                'runtime-dns-progress.json','runtime-dns-progress.pending.json',
                'runtime-traffic-progress.json','runtime-traffic-progress.pending.json',
                'runtime-provider-limit.json','runtime-provider-limit.pending.json')
            private_names += ('desktop-queries.json','desktop-queries.pending.json')
            _windows_private_object(path,sid)
            for name in private_names:
                _windows_private_object(path/name,sid,optional=True)
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
        package_sqlite.require_runtime()
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

    def read_view(self, *, now=None):
        """A caller-owned, physically read-only view of this validated history.

        Never create/migrate/expire data here. Ingestion retains its one writer;
        dashboard reads use their own connection and committed SQLite revision.
        """
        if self.path.is_symlink() or not self.path.is_file() or self.path.stat().st_nlink!=1:
            raise HistoryError('History database must be an owned regular file')
        view=object.__new__(History)
        view.directory=self.directory;view.path=self.path
        view.now=instant(now) if now is not None else self.now
        view.db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True,isolation_level=None)
        view.db.row_factory=sqlite3.Row
        try:
            view.db.execute('PRAGMA query_only=ON')
            if view.db.execute('PRAGMA user_version').fetchone()[0]!=4:
                raise HistoryError('Unsupported history schema; existing data preserved')
        except BaseException:
            view.close();raise
        return view

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
        if version not in (0, 1, 2, 3, 4):
            raise HistoryError('Unsupported history schema; existing data preserved')
        # Dashboard batches retain a committed read snapshot while the single
        # ingestion writer continues. DELETE journals require an exclusive
        # commit lock, turning a valid long read into a collector write failure.
        if self.db.execute('PRAGMA journal_mode=WAL').fetchone()[0].lower()!='wal':
            raise HistoryError('History requires WAL for concurrent dashboard reads')
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
            if version < 4:
                self.db.execute('CREATE TABLE snapshots(id TEXT PRIMARY KEY,kind TEXT NOT NULL,scope TEXT NOT NULL,time INTEGER NOT NULL,end INTEGER NOT NULL,data TEXT NOT NULL,revision INTEGER NOT NULL)')
                self.db.execute('CREATE INDEX snapshots_scope_time ON snapshots(kind,scope,time,end)')
                self.db.execute('PRAGMA user_version=4')
            # Additive, backwards-compatible indexes, not stored metrics or a
            # schema migration. Existing clients can still read the same facts.
            self.db.execute('CREATE INDEX IF NOT EXISTS traffic_dashboard ON traffic(time,application,destination,inbound,outbound,source,identity,port)')
            self.db.execute('CREATE INDEX IF NOT EXISTS traffic_application_time ON traffic(application,time,destination,inbound,outbound,source,identity,port)')
            self.db.execute("CREATE INDEX IF NOT EXISTS traffic_unsupported_time_source ON traffic(time,source) WHERE json_extract(data,'$.destination_status')='unsupported-address-family'")

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
        self.db.execute('DELETE FROM snapshots WHERE end<=?', (floor,))
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

    def import_live_dns(self, raw, scope, endpoint, *, collected):
        """One observed event, never a coverage interval or checkpoint.

        Complete CSV windows replace all live observations in their interval.
        Late stream events already covered by such a window are ignored. No
        cross-format hash heuristic can erase genuinely identical requests.
        """
        time=instant(raw['timestamp'])
        if raw.get('endpointId')!=endpoint or not isinstance(raw.get('question'),str):
            raise HistoryError('Live DNS endpoint scope does not match')
        with self.transaction():
            floor=self._expire();source=self._source('dns',scope,endpoint=endpoint)
            if (time<floor or self._suppressed('dns',source,time) or
                    self.db.execute("SELECT 1 FROM runs WHERE source=? AND state='complete' AND start<=? AND end>? LIMIT 1",
                                    (source,time,time)).fetchone()):
                return {'state':'historical-or-suppressed','source':source}
            revision=self._run(source,time,time+1,{'collected_at_utc':collected},'observed-live')
            identity=digest(raw)
            ordinal=self.db.execute('SELECT coalesce(max(ordinal),0)+1 FROM dns WHERE source=? AND identity=?',
                                    (source,identity)).fetchone()[0]
            self.db.execute('INSERT INTO dns VALUES(?,?,?,?,?,?,?,?)',
                (source,identity,ordinal,time,endpoint,raw['question'],revision,
                 packed({'source':'controld-live-sse','raw':raw})))
        return {'state':'observed-live','source':source,'revision':revision}

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

    @staticmethod
    def _coverage_gaps(intervals,a,b):
        cursor=a;gaps=[]
        for x,y in intervals:
            if y<=cursor:continue
            if x>=b:break
            if x>cursor:gaps.append((cursor,min(x,b)))
            cursor=max(cursor,min(y,b))
        if cursor<b:gaps.append((cursor,b))
        return gaps

    @staticmethod
    def _coverage_union(intervals,x,y):
        merged=[]
        for left,right in intervals:
            if right<x:merged.append((left,right))
            elif y<left:
                merged.append((x,y));x,y=left,right
            else:x,y=min(x,left),max(y,right)
        merged.append((x,y))
        return merged

    def _coverage(self, kind, a, b, selected=None, endpoint=None, *, cache=None):
        # The caller owns this cache for ONE read transaction. Never persist it
        # on History: ingestion and later revisions must see corrected runs.
        cache={} if cache is None else cache
        key=('runs',kind,selected,endpoint)
        prepared=cache.get(key)
        if prepared is None or a<prepared['start'] or b>prepared['end']:
            low=min(a,prepared['start']) if prepared else a
            high=max(b,prepared['end']) if prepared else b
            floor=self.db.execute('SELECT expiry_floor FROM settings').fetchone()[0]
            inputs=[]
            for source,metadata in self.db.execute('SELECT id,metadata FROM sources WHERE kind=?',(kind,)):
                if selected and source!=selected or endpoint is not None and json.loads(metadata).get('endpoint')!=endpoint:continue
                runs=list(self.db.execute('SELECT start,end,state,revision FROM runs WHERE source=? AND end>? AND start<? ORDER BY revision',(source,low,high)))
                complete=[r for r in reversed(runs) if r[2]=='complete']
                covered=[];position=0;attempts=[]
                for x,y,state,revision in reversed(runs):
                    if state=='complete':continue
                    while position<len(complete) and complete[position][3]>revision:
                        left,right=complete[position][:2]
                        covered=self._coverage_union(covered,left,right);position+=1
                    unresolved=self._coverage_gaps(covered,max(x,low,floor),min(y,high))
                    attempts.append((x,y,state,unresolved))
                all_complete=[]
                for x,y,_,_ in complete:all_complete=self._coverage_union(all_complete,x,y)
                inputs.append((source,runs,all_complete,list(reversed(attempts))))
            deleted=list(self.db.execute('SELECT source,start,end FROM suppressions WHERE kind=? AND end>? AND start<?',(kind,low,high)))
            prepared={'start':low,'end':high,'floor':floor,'inputs':inputs,'deleted':deleted}
            cache[key]=prepared
        floor=prepared['floor']
        detail = []
        for source,runs,complete,attempts in prepared['inputs']:
            if not any(x<b and y>a for x,y,_,_ in runs):continue
            gaps=[]
            if a < floor:
                gaps.append({'start': utc(a), 'end': utc(min(b, floor)), 'reason': 'retention-expired'})
            gaps.extend({'start':utc(x),'end':utc(y),'reason':'unobserved'} for x,y in self._coverage_gaps(complete,max(a,floor),b))
            selected_attempts=[{'start':utc(x),'end':utc(y),'state':state,
                'resolved':not any(left<min(y,b) and right>max(x,a,floor) for left,right in unresolved)}
                for x,y,state,unresolved in attempts if y>a and x<b]
            deleted=sum(1 for owner,x,y in prepared['deleted'] if (owner is None or owner==source) and y>a and x<b)
            detail.append({'source': source, 'gaps': gaps, 'incomplete_attempts': selected_attempts, 'deletion_scopes': deleted})
        return {'incomplete': not detail or any(r['gaps'] or any(not attempt['resolved'] for attempt in r['incomplete_attempts']) or r['deletion_scopes'] for r in detail),
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
