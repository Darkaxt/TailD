"""Desktop query/export contracts over real SQLite, including exact counters."""
import csv
import io
import importlib.util
import json
import unittest

import analytics
import test_analytics
START,END=test_analytics.START,test_analytics.END

desktop_api = __import__('desktop_api') if importlib.util.find_spec('desktop_api') else None


class DesktopContractTest(unittest.TestCase):
    setUp=test_analytics.AnalyticsTest.setUp
    request=test_analytics.AnalyticsTest.request
    query=test_analytics.AnalyticsTest.query
    context=test_analytics.AnalyticsTest.context
    def test_progressive_desktop_results_keep_decimal_counters_and_final_order(self):
        api=desktop_api.DesktopAPI(self.store);events=[]
        request={'queries':[self.request(),self.request(kind='dns')]}
        expected=api.dispatch('view-query',request)
        result=api.dispatch('view-query',request,on_result=events.append)
        self.assertEqual(result,expected)
        self.assertEqual([e['index'] for e in events],[1,0])
        self.assertIsInstance(events[1]['result']['data']['data']['total_bytes'],str)
        for event in events:self.assertEqual(event['result'],result['results'][event['index']])
    def test_desktop_revision_query_saved_scope_and_safe_export(self):
        self.assertIsNotNone(desktop_api, 'Desktop query/export boundary missing')
        api = desktop_api.DesktopAPI(self.store)
        request = self.request(view='facts',limit=100)
        batch = api.dispatch('view-query', {'queries':[self.request(), request]})
        revision = batch['revision']
        self.assertEqual(batch['results'][0]['data']['data']['total_bytes'],str(2**53+54))
        self.assertIn(str(2**53+9),[r['inbound_bytes'] for r in batch['results'][1]['data']['rows']])
        saved = {'name':'Synthetic scope','query':request}
        api.dispatch('saved-query',{'action':'save',**saved})
        reopened = desktop_api.DesktopAPI(self.store).dispatch('saved-query',{'action':'list'})
        self.assertEqual(reopened['queries'],[saved])
        exported = api.dispatch('export-query',{'query':request,'revision':revision,'format':'json'})
        decoded = json.loads(exported['content'])
        self.assertEqual(decoded['revision'],revision)
        self.assertEqual(sum(int(r['total_bytes']) for r in decoded['result']['data']['rows']),2**53+54)
        self.assertEqual(decoded['query'],request)
        self.assertEqual(decoded['schema'],'taild-desktop-evidence-v1')
        self.store.import_traffic({**self.traffic,'collected_at_utc':'2026-10-08T10:02:01Z'},'host')
        with self.assertRaises(analytics.QueryError) as stale:
            api.dispatch('export-query',{'query':request,'revision':revision,'format':'csv'})
        self.assertEqual(stale.exception.code,'stale-revision')

    def test_desktop_compound_numeric_values_formula_safety_and_bounded_queries(self):
        self.assertIsNotNone(desktop_api, 'Desktop query/export boundary missing')
        api = desktop_api.DesktopAPI(self.store)
        request = self.request(view='facts',where={'all':[
            {'field':'total_bytes','op':'gt','value':str(2**53)},
            {'field':'destination_port','op':'eq','value':'443'}]})
        batch = api.dispatch('view-query',{'queries':[request]})
        self.assertEqual(batch['results'][0]['data']['total_count'],1)
        hostile = '=HYPERLINK("https://example.invalid")'
        changed = json.loads(json.dumps(self.traffic))
        changed['rows'][0]['application_path'] = hostile
        changed['rows'][0]['provenance']['application_blob_sha256']='hostile-app-identity'
        self.store.import_traffic(changed,'host')
        request = self.request(view='facts',limit=100)
        batch = api.dispatch('view-query',{'queries':[request]})
        exported = api.dispatch('export-query',{'query':request,'revision':batch['revision'],'format':'csv'})
        rows = list(csv.DictReader(io.StringIO(exported['content'])))
        self.assertTrue(any(r['application_path'].startswith("'=") for r in rows))
        self.assertTrue(all(r['aggregation_version']=='taild-metrics-v2' for r in rows))
        self.assertTrue(all(r['scope'] for r in rows))
        self.assertEqual(sum(int(r['total_bytes']) for r in rows),2**53+54)
        self.assertTrue(exported['formula_safe'])
        for command, body in [('view-query',{'queries':[{'sql':'select 1'}]}),
                              ('saved-query',{'action':'save','name':'bad','query':{'token':'secret'}}),
                              ('export-query',{'query':request,'revision':batch['revision'],'format':'html'}),
                              ('view-query',{'queries':[self.request(where={'field':'total_bytes','op':'eq','value':'1;drop table traffic'})]})]:
            with self.assertRaises(analytics.QueryError):
                api.dispatch(command,body)

    def test_desktop_catalog_retention_and_no_implicit_source_mutations(self):
        self.assertIsNotNone(desktop_api, 'Desktop query/export boundary missing')
        api = desktop_api.DesktopAPI(self.store)
        catalog = api.dispatch('view-catalog',{})
        self.assertTrue(any(s['scope']=='host' and s['kind']=='traffic' for s in catalog['sources']))
        self.assertEqual(catalog['health']['retention_days'],7)
        api.dispatch('retention',{'days':14})
        self.assertEqual(self.store.health()['retention_days'],14)
        self.assertEqual(self.query(view='facts')['data']['total_count'],3)

    def test_explicit_refresh_keeps_selected_fact_on_a_new_consistent_revision(self):
        api=desktop_api.DesktopAPI(self.store)
        query=self.request(view='facts',limit=1)
        first=api.dispatch('view-query',{'queries':[query]})
        second=api.dispatch('view-query',{'queries':[{**query,'cursor':first['results'][0]['data']['next_cursor']}]})
        selected=second['results'][0]['data']['rows'][0]['id']
        self.traffic['rows'][0]['inbound_bytes']+=1
        self.store.import_traffic(self.traffic,'host')
        refreshed=api.dispatch('view-query',{'queries':[{**query,'anchor_id':selected},self.request()]})
        self.assertEqual(refreshed['results'][0]['data']['rows'][0]['id'],selected)
        self.assertTrue(refreshed['results'][0]['data']['anchor_present'])
        self.assertEqual(refreshed['results'][0]['data']['page_offset'],1)
        self.assertIsNotNone(refreshed['results'][0]['data']['previous_cursor'])
        self.assertTrue(all(r['revision']==refreshed['revision'] for r in refreshed['results']))

    def test_context_privacy_deletion_prevents_reimport_without_source_mutation(self):
        self.context()
        api=desktop_api.DesktopAPI(self.store)
        self.assertEqual(self.query(kind='context',view='facts')['data']['total_count'],1)
        api.dispatch('delete-snapshots',{'kind':'context','start':START,'end':END})
        self.assertEqual(self.query(kind='context',view='facts')['data']['total_count'],0)
        self.assertTrue(self.context()['suppressed'])
        self.assertEqual(self.query(view='facts')['data']['total_count'],3)

    def test_empty_recent_view_does_not_scan_all_older_traffic_for_health(self):
        source,_,timestamp,application,destination,port,incoming,outgoing,revision,data=self.store.db.execute('SELECT * FROM traffic LIMIT 1').fetchone()
        with self.store.transaction():
            self.store.db.executemany('INSERT INTO traffic VALUES(?,?,?,?,?,?,?,?,?,?)',[
                (source,'older-cost-fixture-'+str(i),timestamp,application,destination,port,incoming,outgoing,revision,data)
                for i in range(5000)])
        instructions=[0]
        def measure():instructions[0]+=100;return 0
        self.store.db.set_progress_handler(measure,100) # Count only; never cancel by time or instruction budget.
        try:
            result=self.engine.batch([self.request(start=END,end='2026-10-08T10:03:00Z')])
        finally:self.store.db.set_progress_handler(None,0)
        self.assertEqual(result['results'][0]['data']['data']['total_bytes'],0)
        self.assertLess(instructions[0],10000,'Source health scanned unrelated older fact payloads')

    def test_operational_health_does_not_materialize_network_facts_or_candidates(self):
        statements=[]
        self.store.db.set_trace_callback(statements.append)
        try:result=self.engine.batch([self.request(view='health')])
        finally:self.store.db.set_trace_callback(None)
        self.assertEqual(result['results'][0]['data']['domain'],'operational-not-network-activity')
        self.assertFalse(any('SELECT f.*' in sql for sql in statements),'Health unnecessarily materialized bounded network facts')
