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

    def seed(self,question,seconds=1,account='current',endpoint='device'):
        observed=(self.now-timedelta(seconds=seconds)).isoformat()
        self.store.import_live_dns({'timestamp':observed,'endpointId':endpoint,
            'question':question,'rrType':'A','action':'0','profileId':'profile'},account,endpoint,collected=self.now.isoformat())

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

    def test_unconfigured_or_untyped_requests_are_rejected(self):
        with closing(self.store.read_view()) as view:
            with self.assertRaisesRegex(ValueError,'explicit-provider-required'):recent_dns.read(view,{},None,'disabled')
            for body in ([],{'queries':[]},{'account':'foreign'},{'endpoint':'../device'},{'endpoint':[]},{'endpoint':None},
                         {'search':42},{'search':'x'*257},{'search':'x\x00y'}):
                with self.subTest(body=body),self.assertRaises(ValueError):recent_dns.read(view,body,self.provider,'connected')
