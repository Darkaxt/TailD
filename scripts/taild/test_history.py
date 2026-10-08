"""Real SQLite contract tests for Stage 4; no live provider or private fixtures."""
from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

try:
    import history
except ModuleNotFoundError:
    history = None
import glasswire
try:
    import ingestion
except ModuleNotFoundError:
    ingestion = None
import test_glasswire

START = '2026-10-07T16:36:40Z'
END = '2026-10-07T16:36:43Z'
NOW = '2026-10-08T00:00:00Z'


class HistoryTest(unittest.TestCase):
    add_row = test_glasswire.GlassWireTest.add_row
    read = test_glasswire.GlassWireTest.read

    def setUp(self):
        test_glasswire.GlassWireTest.setUp(self)
        self.assertIsNotNone(history, 'Durable Stage 4 history is not implemented')
        self.home = self.root / 'owned-history'
        self.store = history.History(self.home, now=NOW)
        self.addCleanup(self.store.close)

    def ingest(self):
        data = self.read()
        return self.store.import_traffic(data, 'synthetic-host')

    def query(self, **filters):
        return self.store.query('traffic', START, END, **filters)

    def dns(self, rows=None, truncated=False, start=START, end=END):
        row = {'source': 'controld-activity-csv', 'raw': {
            'timestamp': '2026-10-07T16:36:41Z', 'endpointId': 'synthetic',
            'question': 'example.invalid', 'action': 'unknown'}}
        return {'source': 'controld-activity-csv', 'collected_at_utc': NOW,
                'query_window': {'start_inclusive': start, 'end_inclusive': end},
                'endpoint_id': 'synthetic', 'truncated': truncated,
                'rows': [copy.deepcopy(row), copy.deepcopy(row)] if rows is None else rows}

    def test_persist_restart_replay_exact_and_filtered(self):
        self.writer.execute('update traffic_stats set inbound_bytes=?', (2**53+7,))
        self.writer.commit()
        self.ingest()
        first = self.query(application_path=r'C:\Synthetic\example.exe')
        self.assertEqual(first['inbound_bytes'], 2**53+7)
        self.assertEqual(first['row_count'], 1)
        self.store.close()
        self.store = history.History(self.home, now=NOW)
        self.addCleanup(self.store.close)
        self.ingest()
        self.assertEqual(self.query()['inbound_bytes'], first['inbound_bytes'])
        self.assertEqual(self.query(application_path='other')['row_count'], 0)
        self.assertEqual(self.store.health()['sources'][0]['complete_through'], END)

    def test_mutation_replaces_not_adds_cumulative_bytes(self):
        self.ingest()
        self.writer.execute('update traffic_stats set inbound_bytes=135,outbound_bytes=2')
        self.writer.commit()
        self.ingest()
        self.assertEqual((self.query()['inbound_bytes'],self.query()['outbound_bytes']), (135,2))

    def test_generation_survives_mutation_and_changes_on_replacement(self):
        before = self.read()['generation']
        self.add_row(1791391002)
        self.assertEqual(before, self.read()['generation'])
        self.writer.close()
        self.stats.rename(self.root / 'retired.db')
        self.writer = sqlite3.connect(self.stats)
        self.addCleanup(self.writer.close)
        self.writer.execute('CREATE TABLE traffic_stats(timestamp INTEGER,app_id INTEGER,remote_host BLOB,remote_port INTEGER,remote_host_region BLOB,protocol INTEGER,flags INTEGER,inbound_bytes INTEGER,outbound_bytes INTEGER,threat_level INTEGER)')
        self.add_row(1791391002)
        self.assertNotEqual(before, self.read()['generation'])

    def test_catalog_selection_rejects_escape_and_ignores_other_scales(self):
        folder=self.root/'stats'
        folder.mkdir()
        self.writer.close()
        self.stats.rename(folder/self.stats.name)
        self.stats=folder/self.stats.name
        self.writer=sqlite3.connect(self.stats)
        self.addCleanup(self.writer.close)
        with closing(sqlite3.connect(self.main)) as db:
            db.execute('CREATE TABLE stats_databases(id INTEGER,filename BLOB,timestamp INTEGER,expire_time INTEGER,scale INTEGER)')
            db.execute('INSERT INTO stats_databases VALUES(1,?,1791331200,1791504000,1)', (self.stats.name.encode(),))
            db.execute('INSERT INTO stats_databases VALUES(2,?,1791331200,1791504000,2)',(b'glasswire_stats_30sec_1791331200.db',))
            db.commit()
        catalog = glasswire.discover(self.root)
        self.assertEqual([x['path'] for x in catalog['databases']], [str(self.stats)])
        with closing(sqlite3.connect(self.main)) as db:
            db.execute('UPDATE stats_databases SET filename=? WHERE id=1',(b'../glasswire_stats_1sec_1791331200.db',))
            db.commit()
        with self.assertRaises(glasswire.GlassWireError):
            glasswire.discover(self.root)

    def test_identical_dns_multiset_overlap_late_arrival_and_correction(self):
        data = self.dns()
        self.store.import_dns(data, 'account', 'synthetic')
        self.store.import_dns(data, 'account', 'synthetic')
        self.assertEqual(self.store.query('dns',START,END)['row_count'], 2)
        data['rows'].append(copy.deepcopy(data['rows'][0]))
        self.store.import_dns(data, 'account', 'synthetic')
        self.assertEqual(self.store.query('dns',START,END)['row_count'], 3)
        data['query_window']['start_inclusive'] = '2026-10-07T16:36:41Z'
        data['rows'].pop()
        self.store.import_dns(data, 'account', 'synthetic')
        self.assertEqual(self.store.query('dns',START,END)['row_count'], 2)

    def test_truncation_does_not_erase_or_advance_complete_checkpoint(self):
        self.store.import_dns(self.dns(), 'account', 'synthetic')
        data = self.dns([], True, END, '2026-10-07T16:36:45Z')
        self.store.import_dns(data, 'account', 'synthetic')
        result = self.store.query('dns',START,'2026-10-07T16:36:45Z')
        self.assertEqual(result['row_count'], 2)
        self.assertTrue(result['coverage']['incomplete'])
        self.assertEqual(self.store.health()['sources'][0]['complete_through'], END)

    def test_delete_application_and_interval_suppress_replay(self):
        self.ingest()
        self.store.delete('traffic', START, END, application_path=r'C:\Synthetic\example.exe')
        self.ingest()
        self.assertEqual(self.query()['row_count'], 0)
        self.store.import_dns(self.dns(), 'account', 'synthetic')
        self.store.delete('dns', START, END)
        self.store.import_dns(self.dns(), 'account', 'synthetic')
        self.assertEqual(self.store.query('dns',START,END)['row_count'], 0)

    def test_retention_prevents_expired_replay_on_restart(self):
        self.ingest()
        self.store.close()
        self.store = history.History(self.home, now='2026-10-16T00:00:00Z')
        self.addCleanup(self.store.close)
        self.ingest()
        self.assertEqual(self.query()['row_count'], 0)
        self.assertTrue(self.query()['coverage']['incomplete'])

    def test_unknown_schema_keeps_existing_history(self):
        self.ingest()
        self.writer.execute('alter table traffic_stats rename column inbound_bytes to changed')
        self.writer.commit()
        with self.assertRaises(glasswire.GlassWireError):
            self.ingest()
        self.assertEqual(self.query()['inbound_bytes'], 100)

    def test_parameter_bound_query_rejects_unknown_fields(self):
        self.ingest()
        self.assertEqual(self.query(application_path="' OR 1=1 --")['row_count'], 0)
        with self.assertRaises(history.HistoryError):
            self.query(arbitrary_sql='drop table traffic')

    def test_unprivate_existing_directory_and_repo_location_rejected(self):
        if sys.platform == 'win32':
            subprocess.run(['icacls', str(self.root), '/grant', '*S-1-1-0:(OI)(CI)R'], check=True, capture_output=True)
        else:
            self.root.chmod(0o755)
        with self.assertRaises(history.HistoryError):
            history.History(self.root, now=NOW)
        with self.assertRaises(history.HistoryError):
            history.History(Path(__file__).parent / 'forbidden-history', now=NOW)

    def test_rowid_reuse_and_midnight_rotation_preserve_old_facts(self):
        self.ingest()
        self.writer.execute('delete from traffic_stats')
        self.writer.commit()
        self.add_row(1791391002, incoming=7)
        self.ingest()
        self.assertEqual(self.query()['inbound_bytes'], 107)
        old = self.stats
        self.stats = self.root / 'glasswire_stats_1sec_1791417600.db'
        self.writer.close()
        with closing(sqlite3.connect(old)) as src, closing(sqlite3.connect(self.stats)) as dst:
            src.backup(dst)  # Synthetic closed fixture only, never a live source copy.
        self.writer = sqlite3.connect(self.stats)
        self.addCleanup(self.writer.close)
        self.writer.execute('delete from traffic_stats')
        self.writer.commit()
        self.add_row(1791391002, incoming=9)
        self.ingest()
        self.assertEqual(self.query()['inbound_bytes'], 116)
        self.assertEqual(len(self.store.health()['sources']), 2)

    def test_crash_before_and_after_commit_facts_checkpoint_atomic(self):
        data = self.read()
        # Child intercepts the real transaction's COMMIT only, after all writes.
        # os._exit exercises SQLite crash recovery, not an exception rollback.
        script = '''
import sys,json,sqlite3,os
import history
payload=json.load(sys.stdin)
store=history.History(payload['home'],now=payload['now'])
class CrashConnection(sqlite3.Connection):
 def execute(self,sql,*args):
  if sql == 'COMMIT' and payload['before']:
   os._exit(23)
  result=super().execute(sql,*args)
  if sql == 'COMMIT':
   os._exit(24)
  return result
store.db.close()
store.db=sqlite3.connect(store.path,isolation_level=None,factory=CrashConnection)
store.db.row_factory=sqlite3.Row
store.import_traffic(payload['data'],'synthetic-host')
'''
        for before in (True, False):
            child = subprocess.run([sys.executable, '-B', '-c', script], input=json.dumps(
                {'home':str(self.home),'now':NOW,'data':data,'before':before}), text=True,
                capture_output=True, cwd=Path(__file__).parent)
            self.assertEqual(child.returncode, 23 if before else 24, child.stderr)
            self.assertEqual(self.query()['row_count'], 0 if before else 1)
            self.assertEqual(len(self.store.health()['sources']), 0 if before else 1)
        self.ingest()
        self.assertEqual(self.query()['inbound_bytes'], 100)

    def test_migration_existing_v1_and_future_schema_fail_closed(self):
        self.ingest()
        self.store.db.execute('drop table suppressions')
        self.store.db.execute('alter table settings drop column revision')
        self.store.db.execute('pragma user_version=1')
        self.store.close()
        self.store = history.History(self.home,now=NOW)
        self.addCleanup(self.store.close)
        self.assertEqual(self.store.health()['schema_version'], 3)
        self.assertEqual(self.query()['inbound_bytes'], 100)
        self.store.db.execute('pragma user_version=99')
        with self.assertRaises(history.HistoryError):
            unexpected = history.History(self.home,now=NOW)
            self.addCleanup(unexpected.close)
        self.assertEqual(self.store.db.execute('pragma user_version').fetchone()[0],99)

    def test_failed_slice_and_source_expiry_gaps_do_not_jump_checkpoint(self):
        self.store.import_dns(self.dns(), 'account', 'synthetic')
        self.store.record_gap('dns','account',END,'2026-10-07T16:36:44Z','source-expired',endpoint='synthetic')
        self.store.import_dns(self.dns([], start='2026-10-07T16:36:44Z',end='2026-10-07T16:36:46Z'), 'account','synthetic')
        self.assertEqual(self.store.health()['sources'][0]['complete_through'],END)
        self.assertTrue(self.store.query('dns',START,'2026-10-07T16:36:46Z')['coverage']['incomplete'])

    def test_integer_sum_exceeding_sqlite_int64_is_exact(self):
        self.writer.execute('update traffic_stats set inbound_bytes=?', (2**63-1,))
        self.writer.commit()
        self.add_row(1791391002,incoming=2**63-1)
        self.ingest()
        self.assertEqual(self.query()['inbound_bytes'], 2**64-2)

    def test_successful_reconciliation_resolves_previous_incomplete_attempt(self):
        data = self.dns(truncated=True)
        self.store.import_dns(data,'account','synthetic')
        self.assertTrue(self.store.query('dns',START,END)['coverage']['incomplete'])
        self.store.import_dns(self.dns(),'account','synthetic')
        self.assertFalse(self.store.query('dns',START,END)['coverage']['incomplete'])

    def test_bounded_provider_splits_preserve_equal_events_and_irreducible_gap(self):
        self.assertIsNotNone(ingestion,'On-demand ingestion command missing')
        def fetch(start,end):
            capped = history.instant(end)-history.instant(start)>1000000
            return self.dns([] if capped else None,capped,start,end)
        # Restrict the synthetic equal rows to the only second that owns them.
        def bounded(start,end):
            data = fetch(start,end)
            data['rows'] = [r for r in data['rows'] if history.instant(start)<=history.instant(r['raw']['timestamp'])<history.instant(end)]
            return data
        ingestion.dns_windows(self.store,'account','synthetic',START,END,bounded)
        self.assertEqual(self.store.query('dns',START,END)['row_count'],2)
        self.assertFalse(self.store.query('dns',START,END)['coverage']['incomplete'])
        def always_capped(start,end):
            return self.dns([],True,start,end)
        ingestion.dns_windows(self.store,'capped-account','synthetic',START,END,always_capped)
        self.assertTrue(self.store.query('dns',START,END)['coverage']['incomplete'])

    def test_cli_exact_strings_and_non_overwriting_private_export(self):
        self.assertIsNotNone(ingestion,'On-demand ingestion command missing')
        # CLI uses the actual clock; keep this fixture valid on future CI runs.
        current = int(history.controld.utc_now().timestamp())
        a,b = history.utc((current-1)*1000000),history.utc((current+1)*1000000)
        data = self.read()
        data['query_window'] = {'start_inclusive':a,'end_exclusive':b}
        data['rows'][0]['timestamp_raw'] = current
        data['rows'][0]['timestamp_utc'] = history.utc(current*1000000)
        self.store.now = history.instant(history.controld.utc_now().isoformat())
        self.store.import_traffic(data,'synthetic-host')
        output = self.home/'query.json'
        child = subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('ingestion.py')),
            '--history',str(self.home),'query','--kind','traffic','--start',a,'--end',b,
            '--output',str(output)],capture_output=True,text=True)
        self.assertEqual(child.returncode,0,child.stderr)
        data = json.loads(output.read_text())
        self.assertEqual(data['inbound_bytes'],'100')
        self.assertNotIn('Synthetic',child.stdout)
        repeat = subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('ingestion.py')),
            '--history',str(self.home),'query','--kind','traffic','--start',a,'--end',b,
            '--output',str(output)],capture_output=True,text=True)
        self.assertNotEqual(repeat.returncode,0)

    def test_deletion_and_retention_change_query_revision(self):
        self.ingest()
        before = self.query()['revision']
        self.store.delete('traffic',START,END)
        self.assertGreater(self.query()['revision'],before)

    def test_existing_database_explicit_public_acl_is_rejected(self):
        if sys.platform != 'win32':
            self.store.path.chmod(0o644)
        else:
            subprocess.run(['icacls',str(self.store.path),'/grant','*S-1-1-0:R'],check=True,capture_output=True)
        with self.assertRaises(history.HistoryError):
            history.History(self.home,now=NOW)

    def test_traffic_ingestion_subdivides_truncated_window(self):
        folder=self.root/'stats'
        folder.mkdir()
        self.writer.close()
        self.stats.rename(folder/self.stats.name)
        self.stats=folder/self.stats.name
        self.writer=sqlite3.connect(self.stats)
        self.addCleanup(self.writer.close)
        with closing(sqlite3.connect(self.main)) as db:
            db.execute('CREATE TABLE stats_databases(id INTEGER,filename BLOB,timestamp INTEGER,expire_time INTEGER,scale INTEGER)')
            db.execute('INSERT INTO stats_databases VALUES(1,?,1791331200,1791504000,1)',(self.stats.name.encode(),))
            db.commit()
        self.add_row(1791391002,incoming=4)
        ingestion.traffic_window(self.store,'synthetic-host',START,END,self.root,limit=1)
        result=self.query()
        self.assertEqual(result['inbound_bytes'],104)
        self.assertFalse(result['coverage']['incomplete'])

    def test_migration_failure_rolls_back_schema_and_preserves_facts(self):
        self.ingest()
        self.store.db.execute('alter table settings drop column revision')
        self.store.db.execute('pragma user_version=1')
        # Existing unexpected table prevents migration 2; do not drop user data
        # or advance the version to work around a genuine incompatibility.
        with self.assertRaises(sqlite3.Error):
            history.History(self.home,now=NOW)
        self.assertEqual(self.store.db.execute('pragma user_version').fetchone()[0],1)
        self.assertEqual(self.store.db.execute('select inbound from traffic').fetchone()[0],100)

    def test_source_retention_gap_does_not_poison_a_later_query(self):
        folder=self.root/'stats'
        folder.mkdir()
        self.writer.close()
        self.stats.rename(folder/self.stats.name)
        self.stats=folder/self.stats.name
        self.writer=sqlite3.connect(self.stats)
        self.addCleanup(self.writer.close)
        with closing(sqlite3.connect(self.main)) as db:
            db.execute('CREATE TABLE stats_databases(id INTEGER,filename BLOB,timestamp INTEGER,expire_time INTEGER,scale INTEGER)')
            db.execute('INSERT INTO stats_databases VALUES(1,?,1791331200,1791504000,1)',(self.stats.name.encode(),))
            db.commit()
        old='2026-10-06T00:00:00Z'
        ingestion.traffic_window(self.store,'synthetic-host',old,END,self.root)
        self.assertTrue(self.store.query('traffic',old,END)['coverage']['incomplete'])
        self.assertFalse(self.query()['coverage']['incomplete'])

    def test_unobserved_endpoint_cannot_inherit_another_endpoints_coverage(self):
        self.store.import_dns(self.dns(),'account','synthetic')
        result=self.store.query('dns',START,END,endpoint='unobserved-endpoint')
        self.assertEqual(result['row_count'],0)
        self.assertTrue(result['coverage']['incomplete'])


if __name__ == '__main__':
    unittest.main()
