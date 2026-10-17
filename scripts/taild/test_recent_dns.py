"""Recent incident observations over real private history, never policy/network."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from contextlib import closing
import tempfile
import unittest
from unittest.mock import patch
import history
import recent_dns


class RecentDNSTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='taild-recent-')
        self.addCleanup(self.temp.cleanup)
        self.now=datetime(2026,10,15,12,tzinfo=timezone.utc)
        self.store=history.History(Path(self.temp.name)/'history',now=self.now.isoformat())
        self.addCleanup(self.store.close)
        self.provider={'account_scope':'current','endpoint':'device'}
        clock=patch('recent_dns.controld.utc_now',return_value=self.now)
        clock.start();self.addCleanup(clock.stop)

    def seed(self,question,seconds=1,account='current',endpoint='device',action='0'):
        observed=(self.now-timedelta(seconds=seconds)).isoformat()
        self.store.import_live_dns({'timestamp':observed,'endpointId':endpoint,
            'question':question,'rrType':'A','action':action,'profileId':'profile'},account,endpoint,collected=self.now.isoformat())

    def read(self,body=None):
        with closing(self.store.read_view()) as view:
            return recent_dns.read(view,body or {},self.provider,'connected')

    def test_current_account_endpoint_time_order_and_limit_are_enforced(self):
        self.seed('foreign-account.invalid',account='foreign')
        self.seed('foreign-endpoint.invalid',endpoint='second')
        self.seed('old.invalid',seconds=901)
        self.seed('future.invalid',seconds=-1)
        for number in range(105):self.seed(f'row-{number}.invalid',seconds=number+1)
        result=self.read()
        self.assertEqual(result['account'],'current');self.assertEqual(result['endpoint'],'device')
        self.assertEqual(result['live_state'],'connected')
        self.assertEqual([r['question'] for r in result['rows']],[f'row-{i}.invalid' for i in range(100)])
        self.assertEqual(len(self.read({'endpoint':'second'})['rows']),1)

    def test_search_reads_stored_facts_without_credentials_network_or_mutation(self):
        self.seed('blocked-example.invalid');self.seed('other.invalid')
        revision=self.store.db.execute('SELECT revision FROM settings').fetchone()[0]
        with patch('controld._body',side_effect=AssertionError('Unexpected network read')),patch('credentials.CredentialStore',side_effect=AssertionError('Unexpected credential read')):
            result=self.read({'search':'blocked-example'})
        self.assertEqual([r['question'] for r in result['rows']],['blocked-example.invalid'])
        self.assertEqual(self.store.db.execute('SELECT revision FROM settings').fetchone()[0],revision)

    def test_visible_decision_labels_and_canonical_values_are_searchable(self):
        for name,action in [('deny.example','0'),('permit.example','1'),('reroute.example','2'),('error.example','-1'),('unclassified.example','99')]:
            self.seed(name,action=action)
        for text,expected in [('Blocked','deny.example'),('bLoCk','deny.example'),('Allowed','permit.example'),
                              ('Bypass','permit.example'),('Redirected','reroute.example'),
                              ('Request failed','error.example'),('Unknown','unclassified.example')]:
            with self.subTest(text=text):
                self.assertEqual([r['question'] for r in self.read({'search':text})['rows']],[expected])

    def test_search_is_or_across_domain_and_decision_and_retains_scope(self):
        self.seed('blocked-in-name.example',action='1')
        self.seed('other.example',action='0')
        self.seed('foreign.example',account='foreign',action='0')
        self.seed('old.example',seconds=901,action='0')
        self.assertEqual({r['question'] for r in self.read({'search':'Blocked'})['rows']},
                         {'blocked-in-name.example','other.example'})
        self.assertEqual(self.read({'search':'not-present'})['rows'],[])

    def test_unconfigured_or_untyped_requests_are_rejected(self):
        with closing(self.store.read_view()) as view:
            with self.assertRaisesRegex(ValueError,'explicit-provider-required'):recent_dns.read(view,{},None,'disabled')
            for body in ([],{'queries':[]},{'account':'foreign'},{'endpoint':'../device'},{'endpoint':[]},{'endpoint':None},
                         {'search':42},{'search':'x'*257},{'search':'x\x00y'}):
                with self.subTest(body=body),self.assertRaises(ValueError):recent_dns.read(view,body,self.provider,'connected')

    def test_question_totals_and_first_seen_include_all_scoped_observations(self):
        self.seed('repeat.invalid',seconds=899)
        for seconds in range(1,106):self.seed('repeat.invalid',seconds=seconds,action='1')
        self.seed('repeat.invalid',seconds=9001)
        self.seed('repeat.invalid',seconds=8*86400)
        self.seed('repeat.invalid',seconds=898,account='foreign')
        self.seed('repeat.invalid',seconds=897,endpoint='other')
        result=self.read({'search':'Allowed'})
        self.assertEqual(len(result['rows']),100)
        for row in result['rows']:
            self.assertEqual(row['total'],107)
            self.assertEqual(row['first_seen'],history.instant((self.now-timedelta(seconds=9001)).isoformat()))
        with closing(self.store.read_view()) as view:
            dashboard=recent_dns.desktop_api.DesktopAPI(view).dispatch('view-query',{'queries':[
                {'kind':'dns','view':'summary','start':result['metrics_start'],'end':result['metrics_end'],
                 'scope':{'account':'current','endpoint':'device'},
                 'where':{'all':[{'field':'question','op':'eq','value':'repeat.invalid'},
                                  {'field':'type','op':'eq','value':'A'}]}}]})
        self.assertEqual(int(dashboard['results'][0]['data']['dns_activity']['events']),107)

    def test_metrics_and_recent_rows_share_a_snapshot_during_new_ingestion(self):
        self.seed('snapshot.invalid',seconds=1)
        dispatch=recent_dns.desktop_api.DesktopAPI.dispatch
        def ingest_after_facts(api,*args,**kwargs):
            result=dispatch(api,*args,**kwargs)
            self.seed('snapshot.invalid',seconds=2)
            return result
        with patch.object(recent_dns.desktop_api.DesktopAPI,'dispatch',ingest_after_facts):
            result=self.read()
        self.assertEqual(result['rows'][0]['total'],1)
        self.assertEqual(result['rows'][0]['first_seen'],result['rows'][0]['timestamp'])
        self.assertEqual(self.read()['rows'][0]['total'],2)
