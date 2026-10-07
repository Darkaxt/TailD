import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import join
except ModuleNotFoundError:
    join = None


class JoinTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(join, 'Local joined-record implementation is missing')
        self.context = {'source': 'taildns-cli-readonly', 'node_id': 'synthetic-node',
                        'os': 'windows', 'tailscale_ips': ['100.64.0.1'],
                        'endpoint_binding': {'method': 'active-TailDNS-local-resolver', 'endpoint_id': 'synthetic-device'}}
        self.traffic = {'source': 'glasswire-sqlite-observed-v1', 'truncated': False,
                        'byte_attribution': 'application-destination-time-bucket',
                        'query_window': {'start_inclusive':'2026-10-07T16:00:00Z','end_exclusive':'2026-10-07T16:05:00Z'},
                        'rows': [{'timestamp_utc': '2026-10-07T16:01:00Z', 'application_id': 42,
                                  'application_path': r'C:\Synthetic\example.exe',
                                  'destination_ip': '198.51.100.12','destination_port':443,
                                  'inbound_bytes':100,'outbound_bytes':20,
                                  'provenance': {'database':'synthetic.db','table':'traffic_stats','rowid':1}}]}
        self.decision = {'source':'controld-activity-csv','raw': {
            'timestamp':'2026-10-07T16:00:58Z','endpointId':'synthetic-device',
            'question':'example.invalid','answers':'198.51.100.12;192.0.2.2','action':'999',
            'rrType':'A','statusCode':'0'}}
        self.decisions = {'source':'controld-activity-csv','rows':[self.decision],
                          'truncated':False,'query_window':{'start_inclusive':'2026-10-07T16:00:00Z','end_inclusive':'2026-10-07T16:05:00Z'}}

    def correlate(self, **options):
        return join.correlate(self.traffic,self.decisions,self.context,'synthetic-device',10,**options)

    def test_ip_preceding_time_and_bound_device_produce_honest_candidate(self):
        result = self.correlate()
        candidate = result['records'][0]['dns_candidates'][0]
        self.assertEqual(candidate['decision'], self.decision)
        self.assertEqual(candidate['age_seconds'], 2)
        self.assertEqual(result['records'][0]['match_status'], 'single-temporal-ip-candidate')
        self.assertFalse(result['deterministic_domain_attribution'])
        self.assertEqual(result['records'][0]['traffic'], self.traffic['rows'][0])
        self.assertEqual(result['byte_attribution'], 'application-destination-time-bucket')

    def test_multiple_domains_keep_one_byte_bucket_and_all_candidates(self):
        second = copy.deepcopy(self.decision)
        second['raw']['question'] = 'other.invalid'
        self.decisions['rows'].append(second)
        result = self.correlate()
        self.assertEqual(len(result['records']),1)
        self.assertEqual(len(result['records'][0]['dns_candidates']),2)
        self.assertEqual(result['records'][0]['match_status'],'ambiguous-temporal-ip-candidates')
        self.assertEqual(result['records'][0]['traffic']['inbound_bytes'],100)

    def test_wrong_endpoint_future_old_and_nonmatching_ip_are_not_joined(self):
        for field,value in [('endpointId','other-device'),('timestamp','2026-10-07T16:01:01Z'),
                            ('timestamp','2026-10-07T16:00:40Z'),('answers','192.0.2.88')]:
            with self.subTest(field=field,value=value):
                decision=copy.deepcopy(self.decision)
                decision['raw'][field]=value
                self.decisions['rows']=[decision]
                self.assertEqual(self.correlate()['records'][0]['dns_candidates'],[])

    def test_unsupported_answers_are_explicit_not_ip_scraped_from_text(self):
        self.decision['raw']['answers']='redirect=198.51.100.12'
        result=self.correlate()
        self.assertEqual(result['unsupported_answer_rows'],1)
        self.assertEqual(result['records'][0]['dns_candidates'],[])

    def test_unknown_address_identity_and_empty_answer_not_fabricated(self):
        self.traffic['rows'][0]['destination_ip']=None
        self.traffic['rows'][0]['application_path']=None
        self.decision['raw']['answers']=''
        result=self.correlate()
        self.assertEqual(result['records'][0]['match_status'],'unusable-traffic-identity-or-address')
        self.assertEqual(result['records'][0]['dns_candidates'],[])

    def test_context_binding_must_match_explicit_endpoint(self):
        self.context['endpoint_binding']['endpoint_id']='other-device'
        with self.assertRaises(join.JoinError): self.correlate()

    def test_source_truncation_and_separate_snapshot_uncertainty_preserved(self):
        self.traffic['truncated']=True
        self.decisions['truncated']=True
        result=self.correlate()
        self.assertTrue(result['traffic_truncated'])
        self.assertTrue(result['decisions_truncated'])
        self.assertIn('separate-source-snapshots',result['uncertainties'])
        self.assertIn('dns-cache-and-ttl-not-established',result['uncertainties'])

    def test_device_capture_whitelists_status_and_proves_actual_dns_binding(self):
        status={'BackendState':'Running','Self':{'ID':'synthetic-node','OS':'windows','HostName':'Synthetic',
                                                'TailscaleIPs':['100.64.0.1'],'PublicKey':'unexported-key'},'Peer':{'private':'unexported'}}
        prefs={'CorpDNS':True,'LocalDNSOverride':True,'LocalDNSResolver':'https://dns.controld.com/synthetic-device',
               'Persist':{'PrivateNodeKey':'unexported-key'}}
        with patch('join.subprocess.check_output',side_effect=[json.dumps(status).encode(),json.dumps(prefs).encode()]):
            result=join.capture_device('synthetic-cli','synthetic-device')
        self.assertEqual(result['node_id'],'synthetic-node')
        self.assertNotIn('unexported',json.dumps(result))
        self.assertEqual(result['endpoint_binding']['endpoint_id'],'synthetic-device')

    def test_disabled_or_wrong_provider_is_not_bound(self):
        status={'BackendState':'Running','Self':{'ID':'node','OS':'windows','TailscaleIPs':['100.64.0.1']}}
        for prefs in ({'CorpDNS':False,'LocalDNSOverride':True,'LocalDNSResolver':'https://dns.controld.com/synthetic-device'},
                      {'CorpDNS':True,'LocalDNSOverride':False,'LocalDNSResolver':'https://dns.controld.com/synthetic-device'},
                      {'CorpDNS':True,'LocalDNSOverride':True,'LocalDNSResolver':'https://other.invalid/synthetic-device'}):
            with patch('join.subprocess.check_output',side_effect=[json.dumps(status).encode(),json.dumps(prefs).encode()]):
                with self.assertRaises(join.JoinError): join.capture_device('synthetic-cli','synthetic-device')

    def test_cli_reads_real_files_exports_without_overwrite_and_prints_only_counts(self):
        status={'BackendState':'Running','Self':{'ID':'node','OS':'windows','TailscaleIPs':['100.64.0.1']}}
        prefs={'CorpDNS':True,'LocalDNSOverride':True,'LocalDNSResolver':'https://dns.controld.com/synthetic-device'}
        with tempfile.TemporaryDirectory(prefix='taild-join-test-',dir='D:/Temp' if Path('D:/Temp').is_dir() else None) as directory:
            root=Path(directory)
            (root/'traffic.json').write_text(json.dumps(self.traffic),encoding='utf-8')
            (root/'decisions.json').write_text(json.dumps(self.decisions),encoding='utf-8')
            args=['--traffic-file',str(root/'traffic.json'),'--decisions-file',str(root/'decisions.json'),
                  '--tailscale-cli','synthetic-cli','--endpoint','synthetic-device',
                  '--max-age-seconds','10','--output',str(root/'joined.json')]
            def call():
                with patch('join.subprocess.check_output',side_effect=[json.dumps(status).encode(),json.dumps(prefs).encode()]):
                    return join.main(args)
            stdout=io.StringIO()
            with contextlib.redirect_stdout(stdout): self.assertEqual(call(),0)
            self.assertEqual(json.loads(stdout.getvalue())['candidate_row_count'],1)
            self.assertNotIn('example.invalid',stdout.getvalue())
            self.assertNotIn('198.51.100.12',stdout.getvalue())
            original=(root/'joined.json').read_bytes()
            with contextlib.redirect_stderr(io.StringIO()): self.assertEqual(call(),1)
            self.assertEqual((root/'joined.json').read_bytes(),original)

    def test_malformed_input_and_invalid_age_rejected_with_sanitized_errors(self):
        for age in (0,-1,float('inf'),float('nan')):
            with self.assertRaises(join.JoinError):
                join.correlate(self.traffic,self.decisions,self.context,'synthetic-device',age)
        self.traffic['rows'][0]['inbound_bytes']=-1
        with self.assertRaises(join.JoinError): self.correlate()


if __name__=='__main__': unittest.main()
