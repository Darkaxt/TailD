"""Stage 5 tests use real private SQLite facts, not mocked query engines."""
import copy
from pathlib import Path
import tempfile
import unittest
import json
import contextlib
import io
from unittest.mock import patch

import history
try:
    import analytics
except ModuleNotFoundError:
    analytics = None

START='2026-10-08T10:00:00Z'
END='2026-10-08T10:02:00Z'


class AnalyticsTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(analytics, 'Stage 5 analytics module is missing')
        self.temp=tempfile.TemporaryDirectory(prefix='taild-metrics-',dir='D:/Temp' if Path('D:/Temp').is_dir() else None)
        self.addCleanup(self.temp.cleanup)
        self.store=history.History(Path(self.temp.name)/'history',now=END)
        self.addCleanup(self.store.close)
        self.engine=analytics.Analytics(self.store)
        self.traffic={'source':'glasswire-sqlite-observed-v1','collected_at_utc':END,
                      'generation':{'traffic_database':{'file_id':'1'},'application_database':{'file_id':'2'}},
                      'query_window':{'start_inclusive':START,'end_exclusive':END},'truncated':False,'rows':[]}
        for i,(ip,incoming,outgoing) in enumerate([('198.51.100.2',2**53+9,3),(None,10,5),('198.51.100.3',20,7)]):
            self.traffic['rows'].append({'timestamp_utc':'2026-10-08T10:00:30Z','timestamp_raw':1791453630,
                'application_id':i,'application_path':None if i==1 else 'synthetic.exe',
                'destination_ip':ip,'destination_port':443,'protocol_raw':6,'flags_raw':0,
                'destination_status':'unsupported-address-family' if ip is None else 'observed-ipv4-little-endian',
                'inbound_bytes':incoming,'outbound_bytes':outgoing,
                'provenance':{'rowid':i+1,'remote_host_blob_sha256':str(i),'application_blob_sha256':str(i)}})
        self.store.import_traffic(self.traffic,'host')
        self.dns={'source':'controld-activity-csv','collected_at_utc':END,'endpoint_id':'endpoint',
                  'query_window':{'start_inclusive':START,'end_exclusive':END},'truncated':False,
                  'rows':[{'source':'controld-activity-csv','raw':{'timestamp':'2026-10-08T10:00:29Z',
                           'endpointId':'endpoint','question':'example.invalid','answers':'198.51.100.2;198.51.100.2',
                           'rrType':'A','action':'unverified-code','trigger':'raw-reason','country':'US'}}]}
        self.store.import_dns(self.dns,'account','endpoint')

    def request(self,**changes):
        return {'kind':'traffic','view':'summary','start':START,'end':END,
                'scope':{'host':'host','account':'account','endpoint':'endpoint'},**changes}

    def test_policy_point_snapshot_is_queryable_without_retroactive_rule_causality(self):
        self.assertTrue(hasattr(self.engine,'record_policy'),'Stage 6 policy history integration missing')
        data={'source':'controld-api-readonly','account_scope':'account','endpoint':'endpoint',
              'profile':'profile','captured_at_utc':'2026-10-08T10:01:00Z',
              'consistency':'separate-api-reads','historical_rule_causality':'not-established',
              'resources':{'restrictions':{'state':'available','data':{'restrictions':['synthetic']}}}}
        result=self.engine.record_policy(data)
        page=self.query(kind='policy',view='facts')['data']['rows']
        self.assertEqual(len(page),1)
        self.assertEqual(page[0]['profile'],'profile')
        self.assertEqual(page[0]['historical_rule_causality'],'not-established')
        self.assertEqual(page[0]['observed_end']-page[0]['timestamp'],1)
        self.assertEqual(self.query(kind='policy',view='facts',end='2026-10-08T10:00:59Z')['data']['rows'],[])
        self.engine.record_policy(data)
        self.assertEqual(len(self.query(kind='policy',view='facts')['data']['rows']),1)
        self.engine.delete_snapshots('policy',START,END,scope='account')
        self.assertTrue(self.engine.record_policy(data)['suppressed'])
        self.assertEqual(self.query(kind='policy',view='facts')['data']['rows'],[])

    def test_policy_rejects_unscoped_secret_or_invented_continuity(self):
        self.assertTrue(hasattr(self.engine,'record_policy'),'Stage 6 policy history integration missing')
        base={'source':'controld-api-readonly','account_scope':'account','endpoint':'endpoint',
              'profile':'profile','captured_at_utc':START,'consistency':'separate-api-reads',
              'historical_rule_causality':'not-established','resources':{}}
        for changes in ({'api_token':'secret'},{'account_scope':''},
                        {'historical_rule_causality':'proven'},{'observed_until_utc':END},
                        {'resources':{'unknown-write-category':{'state':'available'}}}):
            with self.assertRaises(analytics.QueryError):
                self.engine.record_policy({**base,**changes})

    def query(self,**changes):
        return self.engine.batch([self.request(**changes)])['results'][0]

    def context(self,**changes):
        data={'source':'taildns-cli-readonly','captured_at_utc':START,'observed_until_utc':END,
              'coverage_method':'observed-change-stream','node_id':'node','user_id':'user','os':'windows',
              'backend_state':'Running','dns_accepted':True,'local_override':True,'resolver_endpoint':'endpoint','resolver_applied':True,
              'exit_node_id':None,'portal_mode':False,'endpoint_exclusivity':'unverified',**changes}
        return self.engine.record_context('host',data)

    def test_real_store_summary_chart_and_filtered_detail_conserve_exact_bytes(self):
        result=self.engine.batch([self.request(),self.request(view='series',bin_seconds=60),
                                  self.request(view='facts',limit=2)])
        summary,series,page=[r['data'] for r in result['results']]
        self.assertEqual(summary['data']['inbound_bytes'],2**53+39)
        self.assertEqual(sum(b['inbound_bytes'] for b in series['bins']),summary['data']['inbound_bytes'])
        self.assertEqual(page['total_count'],3)
        self.assertIsNotNone(page['next_cursor'])
        selected=self.query(where={'field':'application_path','op':'eq','value':'synthetic.exe'})['data']
        self.assertEqual(selected['data']['inbound_bytes'],2**53+29)
        self.assertTrue(all(r['revision']==result['revision'] for r in result['results']))

    def test_context_not_retrospective_and_candidates_are_versioned_inferences(self):
        unknown=self.query(kind='correlations',view='facts')['data']['rows']
        self.assertEqual(unknown[0]['context_state'],'historical-binding-unknown')
        self.context()
        ordered=self.query(kind='correlations',view='facts')['data']['rows']
        rows=[next(r for r in ordered if r['destination_ip']==ip) for ip in ('198.51.100.2',None,'198.51.100.3')]
        self.assertEqual(rows[0]['correlation_state'],'unique-candidate')
        self.assertEqual(len(rows[0]['candidates']),1)
        self.assertFalse(rows[0]['deterministic_domain_attribution'])
        self.assertTrue(rows[0]['candidate_origin_unproven'])
        self.assertEqual(rows[1]['correlation_state'],'unusable')
        self.assertEqual(rows[2]['correlation_state'],'unmatched')

    def test_shared_answers_multiset_fanout_never_multiplies_traffic(self):
        self.context()
        self.dns['rows'].append(copy.deepcopy(self.dns['rows'][0]))
        self.store.import_dns(self.dns,'account','endpoint')
        summary=self.query()['data']
        self.assertEqual(summary['dns_activity']['events'],2)
        self.assertEqual(summary['correlation_coverage']['ambiguous']['bucket_count'],1)
        self.assertEqual(sum(v['total_bytes'] for v in summary['correlation_coverage'].values()),summary['data']['total_bytes'])
        filtered=self.query(where={'field':'question','op':'eq','value':'example.invalid'})['data']
        self.assertEqual(filtered['data']['inbound_bytes'],2**53+9)

    def test_every_metric_has_honest_denominators_and_unknown_groups(self):
        self.context()
        result=self.query()['data']
        self.assertEqual(result['application_activity']['known_distinct'],2)
        self.assertEqual(result['application_activity']['unknown_buckets'],1)
        self.assertEqual(sum(x['total_bytes'] for x in result['top_applications']),result['data']['total_bytes'])
        self.assertEqual(sum(x['total_bytes'] for x in result['top_destinations']),result['data']['total_bytes'])
        self.assertEqual(result['dns_outcomes']['counts']['unknown'],1)
        self.assertEqual(result['dns_outcomes']['classified_denominator'],0)
        self.assertIsNone(result['dns_outcomes']['block_rate'])
        self.assertEqual(result['dns_questions']['distinct'],1)
        self.assertEqual(result['candidate_domains']['inferred'][0]['question'],'example.invalid')
        self.assertEqual(result['geography_asn']['unknown_bytes'],result['data']['total_bytes'])
        self.assertEqual(result['geography_asn']['capability'],'controld-single-answer-metadata')
        self.assertIn('sources',result['source_health'])

    def test_typed_query_rejects_injection_bad_types_and_unsupported_fields(self):
        bad=[{'sql':'SELECT * FROM traffic'}, {'where':{'field':'DROP TABLE traffic','op':'eq','value':'x'}},
             {'group_by':['application_path;DELETE FROM traffic']}, {'order_by':[{'field':'evil','direction':'asc'}]},
             {'limit':True},{'limit':0},{'bin_seconds':0},{'max_age_seconds':float('nan')},
             {'scope':{'arbitrary':'host'}},{'kind':'dns','where':{'field':'application_path','op':'eq','value':'x'}},
             {'where':{'field':'destination_port','op':'eq','value':'443'}},
             {'where':{'field':'verified_protocol','op':'eq','value':'tcp'}}]
        for change in bad:
            with self.subTest(change=change),self.assertRaises(analytics.QueryError):
                self.query(**change)
        result=self.query(where={'field':'application_path','op':'eq','value':"' OR 1=1 --"})
        self.assertEqual(result['data']['data']['total_bytes'],0)

    def test_predicates_search_groups_order_and_revision_bound_pagination(self):
        predicate={'all':[{'field':'destination_port','op':'in','value':[443,80]},
                          {'any':[{'field':'application_path','op':'contains','value':'synthetic'},
                                  {'field':'application_path','op':'eq','value':None}]}]}
        first=self.query(view='facts',where=predicate,order_by=[{'field':'total_bytes','direction':'desc'}],limit=2)['data']
        self.assertEqual(first['rows'][0]['inbound_bytes'],2**53+9)
        second=self.query(view='facts',where=predicate,order_by=[{'field':'total_bytes','direction':'desc'}],limit=2,cursor=first['next_cursor'])['data']
        self.assertEqual(len({r['id'] for r in first['rows']+second['rows']}),3)
        self.assertEqual(self.query(view='facts',search='SYNTHETIC')['data']['total_count'],2)
        groups=self.query(view='groups',group_by=['application_path'])['data']['groups']
        self.assertEqual(sum(g['total_bytes'] for g in groups),2**53+54)
        self.store.import_traffic(self.traffic,'host')
        with self.assertRaisesRegex(analytics.QueryError,'Stale'):
            self.query(view='facts',where=predicate,order_by=[{'field':'total_bytes','direction':'desc'}],limit=2,cursor=first['next_cursor'])

    def test_context_boundaries_missing_intervals_provider_exit_account_portal_changes(self):
        for changes in ({'resolver_endpoint':'another'}, {'backend_state':'NeedsLogin'}, {'user_id':None},
                        {'portal_mode':True}, {'observed_until_utc':'2026-10-08T10:00:20Z'}):
            with self.subTest(changes=changes):
                self.store.db.execute('DELETE FROM snapshots')
                self.context(**changes)
                rows=self.query(kind='correlations',view='facts')['data']['rows']
                self.assertFalse(any(r['candidates'] for r in rows))
        self.store.db.execute('DELETE FROM snapshots')
        self.context(exit_node_id='first',observed_until_utc='2026-10-08T10:00:29Z')
        self.context(exit_node_id='second',captured_at_utc='2026-10-08T10:00:30Z')
        self.assertFalse(any(r['candidates'] for r in self.query(kind='correlations',view='facts')['data']['rows']))

    def test_partial_and_unobserved_chart_bins_do_not_zero_fill(self):
        result=self.query(view='series',start='2026-10-08T09:59:30Z',end='2026-10-08T10:00:45Z')['data']
        self.assertEqual(result['bins'][0]['represented_microseconds'],30000000)
        self.assertIsNone(result['bins'][0]['rate'])
        self.assertEqual(result['bins'][1]['represented_microseconds'],45000000)
        self.assertEqual(result['bins'][1]['rate']['denominator_microseconds'],45000000)
        self.assertEqual(result['bins'][1]['rate']['numerator_bytes'],2**53+54)
        self.assertEqual(result['bins'][1]['rate']['per_second_scale'],1000000)

    def test_scopes_coverage_unobserved_zero_and_corrections(self):
        self.store.import_traffic(self.traffic,'other-host')
        self.assertEqual(self.query()['data']['data']['total_bytes'],2**53+54)
        absent=self.query(scope={'host':'missing'})
        self.assertEqual(absent['data']['data']['total_bytes'],0)
        self.assertTrue(absent['coverage']['traffic']['incomplete'])
        self.traffic['rows'][0]['inbound_bytes']+=7
        self.store.import_traffic(self.traffic,'host')
        self.assertEqual(self.query()['data']['data']['total_bytes'],2**53+61)

    def test_snapshot_queries_point_capture_privacy_and_retention(self):
        self.context()
        self.assertEqual(self.query(kind='context',view='facts')['data']['total_count'],1)
        self.assertEqual(self.query(kind='policy',view='facts')['capabilities']['policy'],'not-collected')
        with self.assertRaises(analytics.QueryError):
            self.context(private_node_key='must-not-store')
        self.store.delete('traffic',START,END)
        self.assertEqual(self.query(kind='correlations',view='facts')['data']['total_count'],0)

    def test_new_capture_truncates_previous_binding_and_point_capture_does_not_fill_gaps(self):
        self.context()
        self.context(captured_at_utc='2026-10-08T10:00:30Z',resolver_endpoint='another')
        rows=self.query(kind='correlations',view='facts')['data']['rows']
        self.assertFalse(any(r['candidates'] for r in rows))
        self.assertTrue(all(r['context_state']=='observed-binding' for r in rows))
        self.store.db.execute('DELETE FROM snapshots')
        self.context(observed_until_utc=None,coverage_method='point-observation')
        self.assertFalse(any(r['candidates'] for r in self.query(kind='correlations',view='facts')['data']['rows']))

    def test_current_capture_whitelists_configuration_and_unknown_portal_state(self):
        status={'BackendState':'Running','Self':{'ID':'node','UserID':42,'OS':'windows','PublicKey':'private'},'Peer':{'secret':'private'}}
        prefs={'CorpDNS':True,'LocalDNSOverride':True,'LocalDNSResolver':'https://dns.controld.com/endpoint',
               'ExitNodeID':'exit','Persist':{'PrivateNodeKey':'private'}}
        dns={'CurrentTailnet':{'MagicDNSEnabled':True,'MagicDNSSuffix':'example.ts.net'},
             'SplitDNSRoutes':{'example.ts.net.':['100.100.100.100']},'SearchDomains':['example.ts.net']}
        local={'Endpoint':'https://dns.controld.com/endpoint','Configured':True,'Applied':True,'CaptivePortal':False,'ProfileID':'profile'}
        with patch('analytics.subprocess.check_output',side_effect=[json.dumps(x).encode() for x in (status,prefs,dns,local,status,prefs,dns,local)]):
            result=analytics.capture_context('synthetic-cli')
        self.assertNotIn('private',json.dumps(result))
        self.assertEqual(result['resolver_endpoint'],'endpoint')
        self.assertEqual(result['exit_node_id'],'exit')
        self.assertTrue(result['magic_dns_enabled'])
        self.assertEqual(result['resolver_event_coverage'],'unavailable')
        self.assertFalse(result['portal_mode'])
        self.assertTrue(result['resolver_applied'])
        self.engine.record_context('host',result)

    def test_malformed_cursor_and_query_shapes_are_sanitized_errors(self):
        for change in ({'cursor':'not-json'},{'cursor':[]},{'where':[]},{'group_by':[{}]},
                       {'order_by':[{'field':[],'direction':'asc'}]}, {'where':{'field':[],'op':'eq','value':'x'}}):
            with self.subTest(change=change),self.assertRaises(analytics.QueryError):
                self.query(view='facts',**change)

    def test_context_deletion_removes_binding_and_suppresses_replay(self):
        self.context()
        self.engine.delete_snapshots('context',START,END,scope='host')
        self.context()
        self.assertEqual(self.query(kind='context',view='facts')['data']['total_count'],0)

    def test_dns_queries_filter_counts_and_groups_not_traffic_metrics(self):
        result=self.query(kind='dns',where={'field':'question','op':'eq','value':'does-not-exist'})['data']
        self.assertEqual(result['dns_activity']['events'],0)
        self.assertEqual(result['data']['total_bytes'],0)

    def test_future_dns_events_and_answers_before_a_context_change_are_not_candidates(self):
        for stamp in ('2026-10-08T10:00:31Z','2026-10-08T10:00:10Z'):
            self.store.db.execute('DELETE FROM snapshots')
            self.context(captured_at_utc='2026-10-08T10:00:20Z')
            self.dns['rows'][0]['raw']['timestamp']=stamp
            self.store.import_dns(self.dns,'account','endpoint')
            self.assertFalse(any(r['candidates'] for r in self.query(kind='correlations',view='facts')['data']['rows']))

    def test_compound_dns_predicates_use_one_candidate_not_separate_fanout_matches(self):
        self.context()
        second=copy.deepcopy(self.dns['rows'][0])
        second['raw'].update(question='other.invalid',rrType='AAAA')
        self.dns['rows'].append(second)
        self.store.import_dns(self.dns,'account','endpoint')
        predicate={'all':[{'field':'question','op':'eq','value':'example.invalid'},
                          {'field':'type','op':'eq','value':'AAAA'}]}
        self.assertEqual(self.query(where=predicate)['data']['data']['total_bytes'],0)
        alternative={'any':[predicate,{'field':'application_path','op':'eq','value':None}]}
        self.assertEqual(self.query(where=alternative)['data']['data']['total_bytes'],15)

    def test_filtered_unobserved_source_and_endpoint_cannot_borrow_coverage(self):
        for kind,field in (('traffic','source'),('dns','endpoint')):
            result=self.query(kind=kind,where={'field':field,'op':'eq','value':'unobserved'})
            self.assertTrue(result['coverage'][kind]['incomplete'])

    def test_partial_context_delete_cannot_be_reimported_as_a_full_interval(self):
        self.context()
        self.engine.delete_snapshots('context','2026-10-08T10:00:20Z','2026-10-08T10:00:40Z',scope='host')
        self.context()
        self.assertEqual(self.query(kind='context',view='facts')['data']['total_count'],0)

    def test_cli_exports_exact_private_batch_and_prints_only_summary(self):
        output=self.store.directory/'metrics.json'
        args=['--history',str(self.store.directory),'query','--request-stdin','--output',str(output)]
        stdout=io.StringIO()
        with patch('sys.stdin',io.StringIO(json.dumps([self.request(),self.request(view='facts')]))),contextlib.redirect_stdout(stdout):
            self.assertEqual(analytics.main(args),0)
        self.assertNotIn('synthetic.exe',stdout.getvalue())
        self.assertNotIn('example.invalid',stdout.getvalue())
        exported=json.loads(output.read_text())
        self.assertEqual(exported['results'][0]['data']['data']['inbound_bytes'],str(2**53+39))
        self.assertEqual(exported['results'][1]['data']['rows'][0]['inbound_bytes'],str(exported['results'][1]['data']['rows'][0]['fact']['inbound_bytes']))
        original=output.read_bytes()
        with patch('sys.stdin',io.StringIO(json.dumps([self.request()]))),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(analytics.main(args),1)
        self.assertEqual(output.read_bytes(),original)

    def test_device_scope_requires_historical_evidence_not_current_identity(self):
        missing=self.query(scope={'host':'host','device':'node'})
        self.assertEqual(missing['data']['data']['total_bytes'],0)
        self.assertTrue(missing['coverage']['traffic']['incomplete'])
        self.context()
        known=self.query(scope={'host':'host','device':'node'})
        self.assertEqual(known['data']['data']['total_bytes'],2**53+54)
        with self.assertRaises(analytics.QueryError):
            self.query(kind='dns',scope={'device':'node'})

    def test_snapshot_v3_migration_and_retention_preserve_facts(self):
        self.store.db.execute('DROP TABLE snapshots')
        self.store.db.execute('PRAGMA user_version=3')
        self.store._migrate()
        self.assertEqual(self.store.health()['schema_version'],4)
        self.context()
        self.store.now=history.instant('2026-10-16T00:00:00Z')
        self.store.cleanup()
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM snapshots').fetchone()[0],0)
        self.assertEqual(self.query()['data']['data']['total_bytes'],0)

    def test_answer_geography_uses_only_matching_single_answer_not_client_location(self):
        self.context()
        raw=self.dns['rows'][0]['raw']
        raw.update(answerCountryCode='CA',answerASN='64500',sourceCountryCode='US')
        self.store.import_dns(self.dns,'account','endpoint')
        metric=self.query()['data']['geography_asn']
        self.assertEqual(metric['countries'][0]['value'],'CA')
        self.assertEqual(metric['countries'][0]['total_bytes'],2**53+12)
        self.assertEqual(metric['unknown_bytes'],42)
        self.assertEqual(metric['asns'][0]['value'],'64500')
        raw['answers']='198.51.100.2;198.51.100.3'
        self.store.import_dns(self.dns,'account','endpoint')
        mixed=self.query()['data']['geography_asn']
        self.assertEqual(mixed['unknown_bytes'],2**53+54)

    def test_group_order_and_unsupported_option_combinations_are_explicit(self):
        groups=self.query(view='groups',group_by=['application_path'],order_by=[{'field':'total_bytes','direction':'desc'}])['data']['groups']
        self.assertGreater(groups[0]['total_bytes'],groups[1]['total_bytes'])
        for change in ({'view':'summary','group_by':['application_path']},
                       {'view':'facts','bin_seconds':60}, {'view':'series','cursor':'x'}):
            with self.subTest(change=change),self.assertRaises(analytics.QueryError):
                self.query(**change)

    def test_batch_holds_one_real_sqlite_revision_during_a_concurrent_commit(self):
        self.store.db.execute('PRAGMA journal_mode=WAL')
        other=history.History(self.store.directory,now=END)
        self.addCleanup(other.close)
        original=self.engine._query
        changed=copy.deepcopy(self.traffic)
        changed['rows'][0]['inbound_bytes']+=11
        called=[]
        def query(request,revision):
            result=original(request,revision)
            if not called:
                called.append(True)
                other.import_traffic(changed,'host')
            return result
        with patch.object(self.engine,'_query',side_effect=query):
            result=self.engine.batch([self.request(),self.request()])
        self.assertEqual(result['results'][0],result['results'][1])
        self.assertEqual(self.query()['data']['data']['total_bytes'],2**53+65)

    def test_dns_raw_protocol_filters_and_missing_vs_observed_zero_are_explicit(self):
        self.dns['rows'][0]['raw']['protocol']='doh'
        self.store.import_dns(self.dns,'account','endpoint')
        result=self.query(kind='dns',where={'field':'protocol','op':'eq','value':'doh'})
        self.assertEqual(result['data']['dns_activity']['events'],1)
        missing=self.query(scope={'host':'missing'})
        self.assertEqual(missing['value_state'],'unobserved')
        self.assertIsNone(missing['data']['data']['complete_total_bytes'])
        zero=self.query(where={'field':'application_path','op':'eq','value':'absent.exe'})
        self.assertEqual(zero['value_state'],'observed')
        self.assertEqual(zero['data']['data']['complete_total_bytes'],0)

    def test_policy_snapshot_query_contract_without_provider_acquisition(self):
        data={'source':'synthetic-policy-read','endpoint':'endpoint','profile':'synthetic-profile'}
        self.store.db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)',
            ('synthetic-policy','policy','account',history.instant(START),history.instant(END),json.dumps(data),1))
        result=self.query(kind='policy',view='facts',where={'field':'profile','op':'eq','value':'synthetic-profile'})
        self.assertEqual(result['data']['total_count'],1)
        self.assertEqual(result['capabilities']['policy'],'stored-snapshot')

    def test_context_identity_and_boundary_replay_changes_no_traffic_counters(self):
        self.context(observed_until_utc='2026-10-08T10:00:20Z')
        self.context(captured_at_utc='2026-10-08T10:00:20Z',user_id='another-user')
        first=self.query()['data']['data']['total_bytes']
        self.context(captured_at_utc='2026-10-08T10:00:20Z',user_id='another-user')
        self.assertEqual(self.query()['data']['data']['total_bytes'],first)
        # Conflicting observations at the same instant are ambiguous, not chosen
        # by insertion order. A later capture can restore observed continuity.
        self.context(captured_at_utc='2026-10-08T10:00:20Z',user_id='conflicting-user')
        self.assertFalse(any(r['candidates'] for r in self.query(kind='correlations',view='facts')['data']['rows']))

    def test_capture_rejects_identity_change_between_separate_local_reads(self):
        status={'BackendState':'Running','Self':{'ID':'node','UserID':1,'OS':'windows'}}
        next_status=copy.deepcopy(status)
        next_status['Self']['UserID']=2
        with patch('analytics.subprocess.check_output',side_effect=[json.dumps(x).encode() for x in (status,{}, {},{},next_status,{}, {},{})]):
            with self.assertRaisesRegex(analytics.QueryError,'changed'):
                analytics.capture_context('synthetic-cli')

    def test_dns_group_order_uses_event_count_and_health_does_not_count_replays_as_unknowns(self):
        self.dns['rows'].append(copy.deepcopy(self.dns['rows'][0]))
        other=copy.deepcopy(self.dns['rows'][0])
        other['raw']['question']='other.invalid'
        self.dns['rows'].append(other)
        self.store.import_dns(self.dns,'account','endpoint')
        groups=self.query(kind='dns',view='groups',group_by=['question'],order_by=[{'field':'count','direction':'desc'}])['data']['groups']
        self.assertEqual([g['count'] for g in groups],[2,1])
        self.store.import_traffic(self.traffic,'host')
        health=self.query()['data']['source_health']['sources']
        self.assertEqual(sum(s['unsupported_rows'] for s in health if s['kind']=='traffic'),1)
        self.assertEqual(sum(s['unsupported_rows'] for s in health if s['kind']=='dns'),0)


if __name__=='__main__':
    unittest.main()
