"""Real persisted acquisition boundaries, never live provider/device access."""
import json,os
from pathlib import Path
import unittest,uuid
import history,runtime,ingestion

START='2026-10-01T00:00:00Z'
END='2026-10-08T00:00:00Z'
LATER='2026-10-08T00:01:00Z'
PROVIDER={'account_scope':'fixture','endpoint':'fixture','account_type':'personal','instance':'europe'}

class AcquisitionTest(unittest.TestCase):
    def setUp(self):
        self.collector=object.__new__(runtime.Collector)
        self.collector.directory=Path(os.environ['TAILD_PACKAGE_TEST_OUTPUT'])/('acquisition-'+uuid.uuid4().hex)
        self.collector.directory.mkdir(parents=True)
        self.collector.now=lambda:LATER

    def test_completed_dns_backfill_does_not_restart_at_each_poll(self):
        saved={'scope':history.digest(PROVIDER),'start':START,'end':END,'pending_windows':[]}
        self.collector._save_dns_progress(saved)
        self.assertEqual(self.collector._dns_progress(PROVIDER,START,LATER),saved)

    def test_completed_traffic_backfill_does_not_restart_at_each_poll(self):
        saved={'scope':'host','start':START,'end':END,'pending_windows':[]}
        self.collector._save_traffic_progress(saved)
        self.assertEqual(self.collector._traffic_progress('host',START,LATER),saved)

    def test_incomplete_historical_root_survives_hour_boundary(self):
        saved={'scope':history.digest(PROVIDER),'start':START,'end':END,'pending_windows':[[START,END]]}
        self.collector._save_dns_progress(saved)
        self.assertEqual(self.collector._dns_progress(PROVIDER,START,'2026-10-08T03:00:00Z'),saved)

    def test_completed_history_becomes_due_after_one_hour(self):
        self.collector._save_dns_progress({'scope':history.digest(PROVIDER),'start':START,'end':END,'pending_windows':[]})
        self.assertTrue(self.collector._dns_progress(PROVIDER,START,'2026-10-08T01:00:00Z')['pending_windows'])

    def test_recent_high_water_survives_restart_and_catches_offline_interval(self):
        state={'scope':'host','through':END,'reconciled_at':END,'recent':None}
        self.collector._save_poll_state('traffic',state)
        other=object.__new__(runtime.Collector);other.directory=self.collector.directory
        loaded=other._poll_state('traffic','host')
        self.assertEqual(loaded,state)
        self.assertEqual(other._recent_start(loaded,START,'2026-10-08T04:00:00Z'),'2026-10-07T23:58:00Z')
        self.assertIsNone(other._poll_state('traffic','another-host')['through'])

    def test_dense_recent_windows_merge_without_losing_unfinished_work(self):
        old={'start':START,'end':END,'pending_windows':[[START,'2026-10-01T00:01:00Z']]}
        merged=self.collector._recent_pending('dns',old,'2026-10-07T23:58:00Z',LATER,[[END,LATER]])
        self.assertCountEqual(merged['pending_windows'],old['pending_windows']+[[END,LATER]])
        again=self.collector._recent_pending('dns',merged,END,LATER,[[END,LATER]])
        self.assertEqual(again,merged,'Overlapping polls must not grow duplicate continuation work')

    def test_saved_sweep_completion_is_independent_of_recent_high_water(self):
        saved={'scope':history.digest(PROVIDER),'start':START,'end':END,'pending_windows':[]}
        self.collector._save_dns_progress(saved)
        self.collector._save_poll_state('dns',{'scope':history.digest(PROVIDER),'through':LATER,'reconciled_at':END,'recent':None})
        self.assertTrue(self.collector._dns_progress(PROVIDER,START,'2026-10-08T01:00:00Z')['pending_windows'])

    def test_dense_capped_recent_and_history_both_finish_without_recreating_parents(self):
        owner=self.collector;owner.write_error=False
        start,end='2026-10-07T23:59:44Z',END
        owner.now=lambda:end
        store=history.History(owner.directory/'history',now=end);self.addCleanup(store.close)
        calls=[]
        def fetch(left,right):
            calls.append((left,right));a,b=history.bounds(left,right)
            capped=b-a>1000000
            return {'source':'controld-activity-csv','endpoint_id':'fixture','truncated':capped,
                'collected_at_utc':end,'query_window':{'start_inclusive':left,'end_exclusive':right},
                'rows':[] if capped else [{'source':'controld-activity-csv','raw':{
                    'timestamp':history.utc(a),'endpointId':'fixture','question':'dense.invalid','action':'blocked'}}]}
        def collect(left,right,budget,pending=None):
            return ingestion.dns_windows(store,'fixture','fixture',left,right,fetch,max_slices=budget,
                defer_budget=True,resume_pending=pending)
        for _ in range(24):  # Finite binary-tree census, not an operation timeout.
            before=len(calls)
            result=owner._collect_poll('dns',history.digest(PROVIDER),start,end,collect,lambda:True,
                lambda:owner._dns_progress(PROVIDER,start,end),owner._save_dns_progress)
            self.assertLessEqual(len(calls)-before,16)
            if not result['recent_pending_windows'] and not result['backfill_pending_windows']:break
            # Recreate the owner using only atomic on-disk continuations.
            fresh=object.__new__(runtime.Collector);fresh.directory=owner.directory
            fresh.now=lambda:end;fresh.write_error=False;owner=fresh
        self.assertEqual(result['recent_pending_windows'],0)
        self.assertEqual(result['backfill_pending_windows'],0)
        self.assertEqual(store.db.execute('SELECT count(*) FROM dns').fetchone()[0],16)
        self.assertEqual(store.db.execute("SELECT count(*) FROM runs WHERE state='irreducibly-capped'").fetchone()[0],0)

    def test_pause_before_catalog_discovery_does_not_advance_recent_high_water(self):
        self.collector.write_error=False
        state={'scope':'host','through':END,'reconciled_at':END,'recent':None}
        self.collector._save_poll_state('traffic',state)
        def unavailable(*args):return {'pending_windows':None,'slice_attempts':0,'interrupted':True}
        result=self.collector._collect_poll('traffic','host',START,LATER,unavailable,lambda:False,
            lambda:self.fail('No historical work after an admitted pause'),lambda value:None)
        self.assertTrue(result['interrupted'])
        self.assertEqual(self.collector._poll_state('traffic','host'),state)

    def test_completed_empty_catalog_reconciliation_advances_hourly_clock(self):
        owner=self.collector;owner.write_error=False;clock=['2026-10-08T01:00:00Z'];owner.now=lambda:clock[0]
        owner._save_traffic_progress({'scope':'host','start':START,'end':END,'pending_windows':[]})
        owner._save_poll_state('traffic',{'scope':'host','through':END,'reconciled_at':END,'recent':None})
        calls=[]
        def empty(left,right,budget,pending=None):
            calls.append((left,right));return {'slice_attempts':0,'pending_windows':[]}
        def poll():return owner._collect_poll('traffic','host',START,clock[0],empty,lambda:True,
            lambda:owner._traffic_progress('host',START,clock[0]),owner._save_traffic_progress)
        poll();self.assertEqual(len(calls),2)
        calls.clear();clock[0]='2026-10-08T01:01:00Z';poll()
        self.assertEqual(len(calls),1,'An empty completed source must not restart its sweep at every poll')

if __name__=='__main__':unittest.main()
