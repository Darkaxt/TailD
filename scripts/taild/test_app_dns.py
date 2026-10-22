"""Complete process-DNS history/diagnosis contracts; no production data or policies."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import app_dns
import history
import analytics
import reader
import dns_trace
from unittest.mock import patch

START='2026-10-22T12:00:00Z'
END='2026-10-22T13:00:00Z'


class AppDnsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=history.History(Path(self.temp.name)/'private',now=END)
        self.at=history.instant(START)+1000000
        self.batch={'session':'01234567-0123-4123-8123-012345678901','events':[
            {'sequence':1,'at':self.at,'question':'blocked.example','type':1,'status':9003,'results':'',
             'process':{'pid':123,'created':134370000000000000,'path':r'C:\Apps\Example.exe'},
             'binding':{'endpoint':'device','at':START,'method':'active-resolver-point-observation-after-batch'},
             'source':'windows-dns-client-3008'}]}

    def tearDown(self):
        self.store.close();self.temp.cleanup()

    def read(self,**kwargs):
        view=self.store.read_view(now=END)
        try:return app_dns.read(view,{'start':START,'end':END,**kwargs},host='host',provider={'account_scope':'account','endpoint':'device'})
        finally:view.close()

    def provider(self,action,question='blocked.example',endpoint='device',scope='account'):
        with self.store.transaction():
            source=self.store._source('dns',scope,endpoint=endpoint)
            raw={'question':question,'rrType':'A','action':action,'trigger':'filter'}
            self.store.db.execute('INSERT INTO dns VALUES(?,?,?,?,?,?,?,?)',
                (source,history.digest([raw,endpoint,scope]),0,self.at,endpoint,question,self.store._bump(),history.packed({'raw':raw})))

    def test_dns_only_app_negative_lookup_is_unknown_not_blocked(self):
        app_dns.import_batch(self.store,self.batch,'host')
        app_dns.import_batch(self.store,self.batch,'host')
        data=self.read(path=r'c:\apps\EXAMPLE.exe')
        self.assertEqual(len(data['apps']),1)
        self.assertEqual(data['selected']['queries'],1)
        self.assertEqual(data['selected']['inbound'],0)
        self.assertEqual(data['selected']['domains'][0]['outcome'],'unknown')
        self.assertEqual(data['observations'][0]['process']['pid'],123)

    def test_block_is_named_scoped_provider_correlation_not_raw_status(self):
        app_dns.import_batch(self.store,self.batch,'host');self.provider('0')
        d=self.read(path=r'C:\Apps\Example.exe')['selected']['domains'][0]
        self.assertEqual(d['blocked'],1)
        self.assertEqual(d['evidence'][0]['decision_evidence'],'same-endpoint-name-type-time-correlation')
        self.assertEqual(d['evidence'][0]['status'],9003)

    def test_conflicting_and_other_endpoint_provider_decisions_stay_unknown(self):
        app_dns.import_batch(self.store,self.batch,'host');self.provider('0',endpoint='other')
        self.assertEqual(self.read()['apps'][0]['blocked'],0)
        self.provider('0');self.provider('1')
        self.assertEqual(self.read(path=r'C:\Apps\Example.exe')['selected']['domains'][0]['outcome'],'unknown')

    def test_provider_only_events_do_not_create_or_assign_apps(self):
        self.provider('0');self.assertEqual(self.read()['apps'],[])

    def test_unverified_or_mismatched_resolver_binding_does_not_assign_policy(self):
        self.batch['events'][0]['binding']=None
        app_dns.import_batch(self.store,self.batch,'host');self.provider('0')
        self.assertEqual(self.read()['apps'][0]['blocked'],0)

    def test_local_api_parameter_error_is_not_a_provider_block(self):
        self.batch['events'][0]['status']=87
        app_dns.import_batch(self.store,self.batch,'host');self.provider('0')
        self.assertEqual(self.read()['apps'][0]['blocked'],0)

    def test_scope_and_revision_are_enforced(self):
        app_dns.import_batch(self.store,self.batch,'other')
        self.assertEqual(self.read()['apps'],[])
        with self.assertRaises(analytics.QueryError):self.read(revision=-1)

    def test_validation_is_atomic_and_retention_suppression_is_respected(self):
        bad=copy.deepcopy(self.batch);bad['events'].append({})
        with self.assertRaises(ValueError):app_dns.import_batch(self.store,bad,'host')
        self.assertEqual(self.read()['apps'],[])
        with self.store.transaction():self.store.db.execute('INSERT INTO suppressions VALUES(?,?,?,?,NULL)',('app-dns',None,0,self.at+1))
        app_dns.import_batch(self.store,self.batch,'host')
        self.assertEqual(self.read()['apps'],[])

    def test_successful_lookup_does_not_invent_provider_allow_or_connection(self):
        self.batch['events'][0]['status']=0
        app_dns.import_batch(self.store,self.batch,'host')
        data=self.read(path=r'C:\Apps\Example.exe');self.assertEqual(data['selected']['domains'][0]['outcome'],'unknown')
        self.assertEqual(data['destinations'],[])

    def test_equal_weight_estimates_allocate_measured_bytes_once(self):
        import copy
        for i,name in enumerate(('alpha.example','beta.example','alpha.example')):
            fact=copy.deepcopy(self.batch['events'][0]);fact.update(sequence=i+1,question=name,status=0,results='198.51.100.1;')
            self.batch['events'].append(fact)
        self.batch['events']=self.batch['events'][1:]
        app_dns.import_batch(self.store,self.batch,'host')
        with self.store.transaction():
            source=self.store._source('traffic','host',generation={'fixture':'v1'})
            self.store.db.execute('INSERT INTO applications VALUES(?,?,?)',('app',r'C:\Apps\Example.exe','sha'))
            self.store.db.execute('INSERT INTO traffic VALUES(?,?,?,?,?,?,?,?,?,?)',
                (source,'fact',self.at+1000000,'app','198.51.100.1',443,11,5,self.store._bump(),'{}'))
        data=self.read(path=r'C:\Apps\Example.exe')
        self.assertEqual(data['selected']['inbound'],11)
        self.assertEqual(len(data['estimated_domains']),2)
        self.assertTrue(all(r['inbound']=={'numerator':'11','denominator':'2'} for r in data['estimated_domains']))
        self.assertEqual(data['unmatched_bytes'],'0')

    def test_trace_pages_do_not_ack_unread_events_and_stop_preserves_final_batch(self):
        trace=dns_trace.Trace('owner')
        for i in range(300):trace.events.append({'sequence':i+1})
        trace.sequence=300;trace.state='observing'
        first=trace.read(0)
        self.assertEqual(first['sequence'],128)
        self.assertEqual(first['latest_sequence'],300)
        trace.close=lambda:None
        source=reader.GlassWireSource(owner_sid='owner');source.dns_trace=trace
        final=source.dispatch({'op':'app-dns','enabled':False,'session':trace.session,'after':128})
        self.assertEqual(final['sequence'],256)
        self.assertIsNotNone(source.dns_trace)
        source.dispatch({'op':'app-dns','enabled':False,'session':trace.session,'after':300})
        self.assertIsNone(source.dns_trace)

    def test_source_rejects_arbitrary_operations_and_missing_owner(self):
        source=reader.GlassWireSource()
        with self.assertRaises(reader.ReaderError):source.dispatch({'op':'app-dns','enabled':True,'session':None,'after':0})
        with self.assertRaises(reader.ReaderError):source.dispatch({'op':'app-dns','enabled':True,'session':None,'after':0,'provider':'arbitrary'})

    def test_owning_runtime_dispatch_read_export_delete_and_precision(self):
        import runtime
        collector=runtime.Collector(Path(self.temp.name)/'runtime',None,now=lambda:END)
        collector.start()
        try:
            collector._commit(lambda:app_dns.import_batch(collector.store,self.batch,'local-windows'))
            query={'start':START,'end':END,'path':r'C:\Apps\Example.exe'}
            result=collector.dispatch({'op':'app-dns-read','body':query})
            self.assertEqual(result['selected']['queries'],1)
            self.assertIsInstance(result['observations'][0]['process']['created'],str)
            export=collector.dispatch({'op':'app-dns-export','body':{**query,'revision':result['revision'],'format':'json'}})
            self.assertEqual(json.loads(export['content'])['selected']['queries'],1)
            collector.dispatch({'op':'app-dns-delete','body':{'confirm':True}})
            self.assertEqual(collector.dispatch({'op':'app-dns-read','body':query})['apps'],[])
        finally:collector.close()

if __name__=='__main__':unittest.main()
