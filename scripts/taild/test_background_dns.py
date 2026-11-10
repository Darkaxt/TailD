"""Background account collection and two-hour secondary expiry use real history."""
import json
from contextlib import contextmanager
from datetime import datetime,timezone
import threading
import unittest
from unittest.mock import patch
import controld
import history
import runtime
import test_runtime
import test_selected_dns
PROVIDER=test_selected_dns.PROVIDER


@unittest.skipUnless(__import__('os').name=='nt','Windows owning-user runtime')
class BackgroundDNSTest(unittest.TestCase):
    setUp=test_runtime.RuntimeTest.setUp
    add_row=test_runtime.RuntimeTest.add_row
    stop_reader=test_runtime.RuntimeTest.stop_reader
    slice=staticmethod(test_selected_dns.SelectedDNSTest.slice)
    finished=test_selected_dns.SelectedDNSTest.finished

    @contextmanager
    def source(self,fetch=None,devices=('beacon','edge','tablet')):
        with test_selected_dns.SelectedDNSTest.source(self,fetch,devices,background=True):yield

    def next_round(self,done):
        done.clear()
        with self.collector.condition:
            self.collector.due['dns']=0;self.collector.condition.notify()
        self.assertTrue(done.wait(10),'Diagnostic: next background round incomplete')

    def test_all_endpoints_collect_without_a_window_and_continue_after_window_close(self):
        done=threading.Event();original=self.collector._deliver;calls=[]
        def delivered(store,command):
            original(store,command)
            if command[0]=='_finished' and command[1]=='dns':done.set()
        def fetch(*args,**kwargs):calls.append((kwargs['endpoint'],args[3],args[4]));return self.slice(*args,**kwargs)
        with patch.object(controld,'utc_now',return_value=datetime(2026,10,8,tzinfo=timezone.utc)), \
             patch.object(self.collector,'_deliver',delivered),self.source(fetch,devices=('beacon','edge','tablet')):
            self.assertTrue(done.wait(10),'Diagnostic: background DNS round incomplete')
            self.assertFalse(self.collector.window_attached)
            self.assertEqual({row[0] for row in calls},{'beacon','edge','tablet'})
            self.assertLessEqual(len(calls),16)
            for endpoint in ('edge','tablet'):
                result=self.collector.dispatch({'op':'recent-dns','body':{'endpoint':endpoint}})
                self.assertEqual([r['question'] for r in result['rows']],[endpoint+'.invalid'])
                self.assertEqual(result['observation']['state'],'polling')
                self.assertTrue(all(history.instant(left)>=history.instant('2026-10-07T22:00:00Z')
                    for current,left,_ in calls if current==endpoint))
            self.collector.command('window-opened');self.collector.command('window-closed')
            calls.clear();self.next_round(done)
            self.assertIn('edge',{row[0] for row in calls})
            self.assertEqual(self.collector.config['provider'],PROVIDER)

    def test_large_inventory_rotates_with_a_shared_sixteen_request_budget(self):
        done=threading.Event();original=self.collector._deliver;calls=[]
        def delivered(store,command):
            original(store,command)
            if command[0]=='_finished' and command[1]=='dns':done.set()
        def fetch(*args,**kwargs):calls.append(kwargs['endpoint']);return self.slice(*args,**kwargs)
        devices=['beacon']+[f'device-{i:02}' for i in range(20)]
        observed=set()
        with patch.object(self.collector,'_deliver',delivered),self.source(fetch,devices=devices):
            self.assertTrue(done.wait(10),'Diagnostic: first account round incomplete')
            for _ in range(4):
                self.assertLessEqual(len(calls),16);observed.update(calls)
                calls.clear();self.next_round(done)
            observed.update(calls);self.assertEqual(observed,set(devices))

    def test_opening_background_endpoint_reuses_its_current_acquisition(self):
        entered=threading.Event();release=threading.Event();done=threading.Event();calls=[]
        original=self.collector._deliver
        def delivered(store,command):
            original(store,command)
            if command[0]=='_finished' and command[1]=='dns':done.set()
        def fetch(*args,**kwargs):
            calls.append((kwargs['endpoint'],threading.current_thread().name))
            if kwargs['endpoint']=='edge':entered.set();release.wait()
            return self.slice(*args,**kwargs)
        with patch.object(self.collector,'_deliver',delivered),self.source(fetch,devices=('beacon','edge')):
            try:
                self.assertTrue(entered.wait(10),'Diagnostic: original background read not entered')
                self.collector.dispatch({'op':'recent-dns-observe','body':{'endpoint':'edge','owner':'fixture-view'}})
                self.collector.command('state')  # writer processed the queued selection
                self.assertIsNone(self.collector.recent_thread)
                release.set();self.assertTrue(done.wait(10),'Diagnostic: background acquisition incomplete')
                result=self.collector.dispatch({'op':'recent-dns','body':{'endpoint':'edge'}})
                self.assertEqual([r['question'] for r in result['rows']],['edge.invalid'])
                self.assertEqual(result['observation']['state'],'polling')
                self.assertTrue(all(name=='TailD dns acquisition' for endpoint,name in calls if endpoint=='edge'))
            finally:release.set()

    def test_secondary_expiry_preserves_primary_foreign_scope_and_deletion_watermarks(self):
        def seed():
            for scope,endpoint in [('current','beacon'),('current','edge'),('foreign','edge')]:
                for point in ('2026-10-07T21:59:00Z','2026-10-07T23:59:00Z'):
                    self.collector.store.import_live_dns({'timestamp':point,'endpointId':endpoint,
                        'question':'history.invalid','rrType':'A','action':'0'},scope,endpoint,collected='2026-10-08T00:00:00Z')
        self.collector._commit(seed)
        cutoff=history.instant('2026-10-07T22:00:00Z')
        def expire():
            results=[]
            while True:
                result=self.collector.store.expire_secondary_dns_batch('current','beacon',cutoff,limit=1)
                results.append(result)
                if not result['more']:return results
        results=self.collector._commit(expire)
        self.assertTrue(all(r['changed']<=1 for r in results))
        def inspect():
            store=self.collector.store
            rows=store.db.execute("SELECT json_extract(s.metadata,'$.scope'),d.endpoint,count(*) FROM dns d JOIN sources s ON s.id=d.source GROUP BY 1,2").fetchall()
            source=store.db.execute("SELECT id FROM sources WHERE json_extract(metadata,'$.scope')='current' AND json_extract(metadata,'$.endpoint')='edge'").fetchone()[0]
            self.assertTrue(store._suppressed('dns',source,cutoff-1))
            return {(account,endpoint):count for account,endpoint,count in rows}
        self.assertEqual(self.collector._commit(inspect),{('current','beacon'):2,('current','edge'):1,('foreign','edge'):2})

    def test_background_provider_limit_blocks_further_rounds(self):
        done=threading.Event();original=self.collector._deliver;calls=[]
        def delivered(store,command):
            original(store,command)
            if command[0]=='_finished' and command[1]=='dns':done.set()
        def fetch(*args,**kwargs):
            calls.append(kwargs['endpoint'])
            if kwargs['endpoint']=='edge':
                raise controld.ControlDError('Limited',status=429,state='rate-limited',retry_after=120)
            return self.slice(*args,**kwargs)
        with patch.object(self.collector,'_deliver',delivered),self.source(fetch,devices=('beacon','edge','tablet')):
            self.assertTrue(done.wait(10),'Diagnostic: limited account round incomplete')
            before=list(calls)
            self.assertEqual(self.collector.command('state')['sources']['dns']['state'],'rate-limited')
            self.collector.command('refresh',{'wait':True})
            self.assertEqual(calls,before)
            self.assertNotIn('tablet',calls)

    def test_background_endpoint_denial_does_not_replay_or_stop_other_devices(self):
        done=threading.Event();original=self.collector._deliver;calls=[]
        def delivered(store,command):
            original(store,command)
            if command[0]=='_finished' and command[1]=='dns':done.set()
        def fetch(*args,**kwargs):
            calls.append(kwargs['endpoint'])
            if kwargs['endpoint']=='edge':raise controld.ControlDError('Denied',status=403,state='denied')
            return self.slice(*args,**kwargs)
        with patch.object(self.collector,'_deliver',delivered),self.source(fetch,devices=('beacon','edge','tablet')):
            self.assertTrue(done.wait(10),'Diagnostic: denied account round incomplete')
            self.next_round(done)
            self.assertEqual(calls.count('edge'),1)
            self.assertIn('tablet',calls)
            self.assertFalse(self.collector.closing)
            result=self.collector.dispatch({'op':'recent-dns','body':{'endpoint':'edge'}})
            self.assertEqual(result['observation']['state'],'denied')

    def test_pausing_drains_original_background_read_without_starting_another(self):
        entered=threading.Event();release=threading.Event();done=threading.Event();calls=[]
        original=self.collector._deliver
        def delivered(store,command):
            original(store,command)
            if command[0]=='_finished' and command[1]=='dns':done.set()
        def fetch(*args,**kwargs):
            calls.append(kwargs['endpoint'])
            if kwargs['endpoint']=='edge':entered.set();release.wait()
            return self.slice(*args,**kwargs)
        with patch.object(self.collector,'_deliver',delivered),self.source(fetch,devices=('beacon','edge','tablet')):
            try:
                self.assertTrue(entered.wait(10),'Diagnostic: original background read not entered')
                self.collector.command('pause');before=list(calls)
                release.set();self.assertTrue(done.wait(10),'Diagnostic: paused original read did not settle')
                self.assertEqual(calls,before)
                self.assertEqual(self.collector.command('state')['state'],'paused')
            finally:release.set()
