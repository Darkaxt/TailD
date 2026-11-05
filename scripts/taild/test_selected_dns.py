"""Selected endpoint acquisition uses real collector, writer and scoped facts."""
import os
import json
from contextlib import contextmanager
import threading
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
import controld
import history
import runtime
import test_runtime

PROVIDER = {'account_scope':'current', 'endpoint':'beacon', 'account_type':'personal', 'instance':'test'}

@unittest.skipUnless(os.name == 'nt', 'Windows owning-user runtime')
class SelectedDNSTest(unittest.TestCase):
    def setUp(self):
        test_runtime.RuntimeTest.setUp(self)
        clock=patch.object(controld,'utc_now',return_value=datetime(2026,10,8,tzinfo=timezone.utc))
        clock.start();self.addCleanup(clock.stop)
    stop_reader = test_runtime.RuntimeTest.stop_reader
    add_row = test_runtime.RuntimeTest.add_row

    @staticmethod
    def slice(token, account_type, instance, start, end, endpoint=None, **kwargs):
        rows=[]
        for point in ('2026-10-06T00:00:00Z','2026-10-07T23:59:00Z'):
            if history.instant(start)<=history.instant(point)<history.instant(end):
                rows.append({'source':'controld-activity-csv','raw':{'timestamp':point,'endpointId':endpoint,
                    'question':endpoint+'.invalid','rrType':'A','action':'0','profileId':'profile'}})
        return {'source':'controld-activity-csv','collected_at_utc':end,
            'query_window':{'start_inclusive':start,'end_inclusive':end},'endpoint_id':endpoint,'truncated':False,'rows':rows}

    @contextmanager
    def source(self, fetch=None, devices=('beacon','edge','tablet','empty')):
        with patch.object(runtime.credentials.CredentialStore,'read',return_value='fixture-read'), \
             patch.object(controld,'activity_slice',fetch or self.slice), \
             patch.object(controld,'inventory',return_value={'devices':[{'PK':d} for d in devices]}):
            self.collector.command('configure',{'provider':PROVIDER,'dns':True})
            try:yield
            finally:
                # Actual exit precedes removal of the synthetic HTTP/vault boundary.
                self.collector.close()

    def finished(self, event):
        deliver=self.collector._deliver
        def observed(store, command):
            deliver(store,command)
            if command[0]=='_recent_finished':event.set()
        return observed

    def select(self, endpoint='edge', owner='fixture-view', **kwargs):
        return self.collector.dispatch({'op':'recent-dns-observe','body':{'endpoint':endpoint,'owner':owner,**kwargs}})

    def recent(self, endpoint='edge', **kwargs):
        return self.collector.dispatch({'op':'recent-dns','body':{'endpoint':endpoint,**kwargs}})

    def test_another_endpoint_never_inherits_the_configured_stream_status(self):
        self.collector.command('configure', {'provider': PROVIDER})
        self.collector.sources['dns_live'] = {'state':'connected'}
        result = self.collector.dispatch({'op':'recent-dns', 'body':{'endpoint':'edge'}})
        self.assertNotEqual(result['live_state'], 'connected')
        self.assertEqual(result['endpoint'], 'edge')

    def test_old_stream_does_not_label_new_binding_connected_while_it_drains(self):
        entered=threading.Event();release=threading.Event()
        class HeldStream(test_runtime.IsolatedLiveStream):
            def run(self,token,provider,on_event,on_connected):
                on_connected();entered.set();release.wait()
        with patch.object(runtime.live_dns,'Stream',HeldStream),self.source():
            try:
                self.assertTrue(entered.wait(10),'Diagnostic: original stream not entered')
                self.collector.command('configure',{'provider':{**PROVIDER,'endpoint':'edge'}})
                result=self.recent('edge')
                self.assertEqual(result['live_state'],'connecting')
                self.assertEqual(result['observation']['state'],'connecting')
            finally:release.set()

    def test_selected_read_populates_its_cache_without_rebinding_background_collection(self):
        complete = threading.Event()
        original = self.collector._deliver
        def delivered(store, command):
            original(store, command)
            if command[0] == '_recent_finished': complete.set()
        def fetch(token, account_type, instance, start, end, endpoint=None, **kwargs):
            rows = []
            point = '2026-10-07T23:59:00Z'
            if history.instant(start) <= history.instant(point) < history.instant(end):
                rows = [{'source':'controld-activity-csv', 'raw':{'timestamp':point, 'endpointId':endpoint,
                    'question':endpoint+'.invalid', 'rrType':'A', 'action':'0', 'profileId':'profile'}}]
            return {'source':'controld-activity-csv', 'collected_at_utc':end,
                'query_window':{'start_inclusive':start, 'end_inclusive':end},
                'endpoint_id':endpoint, 'truncated':False, 'rows':rows}
        with patch.object(runtime.credentials.CredentialStore, 'read', return_value='fixture-read'), \
             patch.object(controld, 'activity_slice', fetch), \
             patch.object(controld, 'inventory', return_value={'devices':[{'PK':'beacon'}, {'PK':'edge'}]}), \
             patch.object(controld, 'policy_snapshot', return_value={}), \
             patch.object(self.collector, '_deliver', delivered):
            self.collector.command('configure', {'provider':PROVIDER, 'dns':True})
            initial = self.collector.dispatch({'op':'recent-dns-observe', 'body':{'endpoint':'edge', 'owner':'fixture-view'}})
            self.assertEqual(initial['endpoint'], 'edge')
            self.assertTrue(complete.wait(10), 'Diagnostic: selected acquisition did not settle')
            result = self.collector.dispatch({'op':'recent-dns', 'body':{'endpoint':'edge'}})
            self.assertEqual([r['question'] for r in result['rows']], ['edge.invalid'])
            self.assertEqual(result['rows'][0]['total'], 1)
            self.assertEqual(result['observation']['state'], 'polling')
            self.assertNotEqual(result['live_state'], 'connected')
            state = self.collector.command('state')
            self.assertEqual(state['settings']['provider'], PROVIDER)
            self.assertTrue(state['settings']['dns'])
            self.collector.close()

    def test_search_is_local_and_exact_metrics_preserve_selected_scope(self):
        done=threading.Event();calls=[]
        def fetch(*args,**kwargs):
            calls.append(kwargs['endpoint']);return self.slice(*args,**kwargs)
        with self.source(fetch),patch.object(self.collector,'_deliver',self.finished(done)):
            saved=(self.home/'runtime.json').read_bytes()
            self.select();self.assertTrue(done.wait(10),'Diagnostic: selection incomplete')
            before=calls.count('edge')
            result=self.recent(search='edge')
            self.assertEqual([r['question'] for r in result['rows']],['edge.invalid'])
            self.assertEqual(result['rows'][0]['total'],2)
            self.assertEqual(result['rows'][0]['first_seen'],history.instant('2026-10-06T00:00:00Z'))
            self.assertEqual(calls.count('edge'),before,'Search started another provider acquisition')
            self.assertEqual((self.home/'runtime.json').read_bytes(),saved)

    def test_switch_waits_for_owned_operation_and_stale_teardown_cannot_stop_new_selection(self):
        entered=threading.Event();release=threading.Event();done=threading.Event();tablet=threading.Event()
        def fetch(*args,**kwargs):
            if kwargs['endpoint']=='edge' and not entered.is_set():entered.set();release.wait()
            if kwargs['endpoint']=='tablet':tablet.set()
            return self.slice(*args,**kwargs)
        deliver=self.collector._deliver
        def observed(store,command):
            deliver(store,command)
            if command[0]=='_recent_finished' and self.collector.recent_thread is None and self.collector.recent_observation['state']=='polling':done.set()
        with self.source(fetch),patch.object(self.collector,'_deliver',observed):
            try:
                self.select(owner='old-view');self.assertTrue(entered.wait(10),'Diagnostic: source not entered')
                self.select('tablet',owner='new-view')
                self.collector.dispatch({'op':'recent-dns-observe','body':{'owner':'old-view','stop':True}})
                self.assertFalse(tablet.is_set(),'A second selected worker started before the first settled')
                pending=self.recent('tablet')
                self.assertEqual(pending['rows'],[]);self.assertNotEqual(pending['live_state'],'connected')
                self.assertEqual(pending['observation']['state'],'pending')
                release.set();self.assertTrue(done.wait(10),'Diagnostic: latest selection not finished')
                self.assertEqual([r['question'] for r in self.recent('tablet')['rows']],['tablet.invalid'])
                self.assertEqual(self.collector.config['provider'],PROVIDER)
            finally:release.set()

    def test_unowned_endpoint_is_rejected_without_poisoning_collection(self):
        done=threading.Event();calls=[]
        def fetch(*args,**kwargs):calls.append(kwargs['endpoint']);return self.slice(*args,**kwargs)
        with self.source(fetch,devices=('beacon',)),patch.object(self.collector,'_deliver',self.finished(done)):
            self.select();self.assertTrue(done.wait(10),'Diagnostic: rejected selection unsettled')
            result=self.recent()
            self.assertEqual(result['observation']['state'],'endpoint-unavailable')
            self.assertEqual(result['rows'],[])
            self.assertNotIn('edge',calls)
            self.assertFalse(self.collector.closing)

    def test_rate_limit_is_shared_and_explicit_refresh_cannot_bypass_it(self):
        done=threading.Event();calls=[]
        def fetch(*args,**kwargs):
            if kwargs['endpoint']=='edge':
                calls.append('edge')
                raise controld.ControlDError('Limited',status=429,state='rate-limited',retry_after=120)
            return self.slice(*args,**kwargs)
        with self.source(fetch),patch.object(self.collector,'_deliver',self.finished(done)):
            self.select();self.assertTrue(done.wait(10),'Diagnostic: limit unsettled')
            result=self.select(force=True)
            self.assertEqual(result['state'],'rate-limited')
            self.assertEqual(calls,['edge'])
            self.assertEqual(json.loads((self.home/'runtime-provider-limit.json').read_bytes())['until_utc'],'2026-10-08T00:02:00Z')

    def test_provider_denial_is_visible_and_not_automatically_replayed(self):
        done=threading.Event();calls=[]
        def fetch(*args,**kwargs):
            if kwargs['endpoint']=='edge':
                calls.append('edge');raise controld.ControlDError('Denied',status=403,state='denied')
            return self.slice(*args,**kwargs)
        with self.source(fetch),patch.object(self.collector,'_deliver',self.finished(done)):
            self.select();self.assertTrue(done.wait(10),'Diagnostic: denied read unsettled')
            self.assertEqual(self.recent()['observation']['state'],'denied')
            self.assertEqual(self.select()['state'],'denied')
            self.assertEqual(calls,['edge'])
            self.assertFalse(self.collector.closing)

    def test_disabled_analytics_does_not_start_selected_reads(self):
        self.collector.command('configure',{'provider':PROVIDER})
        with patch.object(controld,'inventory',side_effect=AssertionError('Unexpected provider access')):
            self.assertEqual(self.select()['state'],'disabled')
            self.assertIsNone(self.collector.recent_thread)

    def test_selection_admission_and_cache_read_do_not_wait_for_the_writer(self):
        entered=threading.Event();release=threading.Event();admitted=threading.Event();errors=[]
        def hold_writer():
            self.collector._commit(lambda:(entered.set(),release.wait()))
        def read_selection():
            try:
                self.assertEqual(self.select()['endpoint'],'edge')
                self.assertEqual(self.recent()['endpoint'],'edge')
                admitted.set()
            except BaseException as error:errors.append(error)
        with self.source():
            writer=threading.Thread(target=hold_writer);viewer=threading.Thread(target=read_selection)
            try:
                writer.start();self.assertTrue(entered.wait(10),'Diagnostic: held writer not entered')
                viewer.start()
                self.assertTrue(admitted.wait(10),'Selection/cache read waited for unrelated writer work')
                self.assertEqual(errors,[])
                self.assertFalse(release.is_set())
            finally:
                release.set();writer.join()
                if viewer.ident:viewer.join()

    def test_empty_authorized_endpoint_has_its_own_complete_empty_read(self):
        done=threading.Event()
        def fetch(*args,**kwargs):
            result=self.slice(*args,**kwargs)
            if kwargs['endpoint']=='empty':result['rows']=[]
            return result
        with self.source(fetch),patch.object(self.collector,'_deliver',self.finished(done)):
            self.select('empty');self.assertTrue(done.wait(10),'Diagnostic: empty endpoint unsettled')
            result=self.recent('empty')
            self.assertEqual(result['rows'],[])
            self.assertEqual(result['observation']['state'],'polling')
            self.assertFalse(result['coverage']['dns']['incomplete'])

    def test_restart_resumes_captured_selected_history_without_reopening_its_root(self):
        done=threading.Event();calls=[]
        def fetch(*args,**kwargs):
            result=self.slice(*args,**kwargs)
            calls.append((kwargs['endpoint'],args[3],args[4]))
            result['truncated']=history.instant(args[4])-history.instant(args[3])>3600*1000000
            return result
        with self.source(fetch):
            with patch.object(self.collector,'_deliver',self.finished(done)):
                self.select();self.assertTrue(done.wait(10),'Diagnostic: first selected pass unsettled')
            kind='dns-browse-'+history.digest({**PROVIDER,'endpoint':'edge'})
            path=self.home/('runtime-'+kind+'-progress.json')
            first=json.loads(path.read_bytes())
            self.assertTrue(first['pending_windows'])
            self.collector.close()
            self.collector=runtime.Collector(self.home,self.client,now=lambda:'2026-10-08T00:00:00Z',instance='restart-selected')
            self.collector.start();self.addCleanup(self.collector.close);done.clear()
            with patch.object(self.collector,'_deliver',self.finished(done)):
                self.select();self.assertTrue(done.wait(10),'Diagnostic: resumed selected pass unsettled')
            after=json.loads(path.read_bytes())
            self.assertEqual((after['start'],after['end']),(first['start'],first['end']))
            self.assertEqual(calls.count(('edge',first['start'],first['end'])),1)
            self.assertEqual([r['question'] for r in self.recent()['rows']],['edge.invalid'])

    def test_close_drains_the_original_selected_read_before_closing_history(self):
        entered=threading.Event();release=threading.Event();closed=threading.Event()
        def fetch(*args,**kwargs):
            if kwargs['endpoint']=='edge':entered.set();release.wait()
            return self.slice(*args,**kwargs)
        def close():self.collector.close();closed.set()
        with self.source(fetch):
            closer=threading.Thread(target=close)
            try:
                self.select();self.assertTrue(entered.wait(10),'Diagnostic: source not entered')
                closer.start()
                with self.collector.condition:self.collector.condition.wait_for(lambda:self.collector.closing)
                self.assertFalse(closed.is_set(),'Close abandoned an owned provider operation')
                release.set();closer.join()
                self.assertTrue(closed.is_set());self.assertIsNone(self.collector.recent_thread)
            finally:
                release.set()
                if closer.ident:closer.join()

if __name__ == '__main__': unittest.main()
