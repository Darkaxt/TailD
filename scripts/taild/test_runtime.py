"""Collector lifecycle/query integration diagnostics; no installed automation."""
from contextlib import closing
import http.client
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import threading
import unittest
import uuid
from unittest.mock import patch

import history
import controld
import ingestion
import reader
import test_glasswire

runtime = __import__('runtime') if importlib.util.find_spec('runtime') else None


@unittest.skipUnless(os.name == 'nt', 'Windows owning-user runtime')
class RuntimeTest(unittest.TestCase):
    add_row = test_glasswire.GlassWireTest.add_row

    def setUp(self):
        self.assertIsNotNone(runtime, 'Opt-in collector/query lifecycle is missing')
        test_glasswire.GlassWireTest.setUp(self)
        self.writer.close()
        (self.root/'stats').mkdir()
        self.stats = self.stats.replace(self.root/'stats'/self.stats.name)
        with closing(sqlite3.connect(self.main)) as db:
            db.execute('CREATE TABLE stats_databases(filename BLOB,timestamp INTEGER,expire_time INTEGER,scale INTEGER)')
            db.execute('INSERT INTO stats_databases VALUES(?,1791331200,1791504000,1)', (self.stats.name.encode(),))
            db.commit()
        name = 'test-' + uuid.uuid4().hex
        self.server = reader.PipeServer(name, reader.current_sid(), reader.GlassWireSource(self.root))
        self.reader_thread = threading.Thread(target=self.server.serve)
        self.reader_thread.start()
        self.addCleanup(self.stop_reader)
        self.assertTrue(self.server.ready.wait(10), 'Diagnostic: reader startup incomplete')
        self.home = self.root/'history'
        self.client = reader.PipeClient(name)
        self.addCleanup(self.client.close)
        self.collector = runtime.Collector(self.home, self.client,
            now=lambda:'2026-10-08T00:00:00Z', instance=name)
        self.collector.start()
        self.addCleanup(self.collector.close)

    def stop_reader(self):
        self.server.stop()
        self.reader_thread.join()

    def post(self, path, body, headers=None):
        session = self.collector.session()
        connection = http.client.HTTPConnection('127.0.0.1', session['port'])
        headers = headers or {'Authorization':'Bearer '+session['token'],
                               'Origin':session['origin'], 'Content-Type':'application/json'}
        try:
            connection.request('POST', path, json.dumps(body), headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def query(self):
        return self.post('/api/query', {'queries':[{'kind':'traffic','start':'2026-10-07T16:36:40Z',
            'end':'2026-10-07T16:36:43Z','view':'facts','limit':10}]})

    def test_opt_in_acquire_query_pause_resume_restart_without_duplicates(self):
        self.assertEqual(self.collector.command('state')['state'], 'disabled')
        self.collector.command('configure', {'traffic':True})
        self.collector.command('refresh')
        status, result = self.query()
        self.assertEqual(status, 200)
        self.assertEqual(result['results'][0]['data']['total_count'], 1)
        self.collector.command('pause')
        self.assertEqual(self.collector.command('state')['state'], 'paused')
        # Closing a web client above did not disable the collector.
        self.collector.command('resume')
        self.collector.command('refresh')
        self.assertEqual(self.query()[1]['results'][0]['data']['total_count'], 1)
        self.collector.close()
        self.collector = runtime.Collector(self.home, self.client,
            now=lambda:'2026-10-08T00:00:00Z', instance=uuid.uuid4().hex)
        self.collector.start()
        self.addCleanup(self.collector.close)
        self.collector.command('refresh')
        self.assertEqual(self.query()[1]['results'][0]['data']['total_count'], 1)
        self.assertNotIn(self.collector.session()['token'], (self.home/'runtime.json').read_text())

    def test_status_observer_sharing_conflict_does_not_stop_source_collection(self):
        import win32con,win32file,win32api
        attempted=threading.Event();errors=[];replace=Path.replace
        target=self.home/'runtime-status.json'
        # This is an actual Windows observer handle that denies delete sharing,
        # not a mocked source/disk failure. Atomic status replacement must fail.
        handle=win32file.CreateFile(str(target),win32con.GENERIC_READ,
            win32con.FILE_SHARE_READ|win32con.FILE_SHARE_WRITE,None,win32con.OPEN_EXISTING,0,None)
        def observed(path,destination):
            try:return replace(path,destination)
            except OSError as error:
                if path.name=='runtime-status.pending.json':errors.append(error.winerror);attempted.set()
                raise
        try:
            with patch.object(Path,'replace',observed):
                self.collector.command('configure',{'traffic':True})
                attempted.wait()
                state=self.collector.command('state')
                self.assertTrue(errors and set(errors)<={5,32},errors)
                self.assertNotEqual(state['state'],'write-error','Diagnostic sharing conflict stopped data acquisition')
                self.collector.command('refresh')
                self.assertEqual(self.query()[1]['results'][0]['data']['total_count'],1)
        finally:win32api.CloseHandle(handle)

    def test_actual_window_detach_preserves_opt_in_but_stops_disabled_collector(self):
        self.collector.dispatch({'op':'window-opened'})
        self.collector.command('configure', {'traffic':True})
        self.collector.command('refresh')
        detached = self.collector.dispatch({'op':'window-closed'})
        self.assertTrue(detached['collector_continues'])
        self.collector.after_receipt({'op':'window-closed'})
        self.assertFalse(self.collector.closing)
        self.assertEqual(self.query()[0], 200)
        # Reopening has no implicit opt-in/disable side effect.
        self.assertTrue(self.collector.dispatch({'op':'state'})['settings']['traffic'])
        self.collector.command('configure', {'traffic':False})
        detached = self.collector.dispatch({'op':'window-closed'})
        self.assertFalse(detached['collector_continues'])
        self.collector.after_receipt({'op':'window-closed'})
        self.assertTrue(self.collector.closed.wait(10), 'Diagnostic: stop not observed')

    def test_read_only_client_disconnect_is_not_a_window_close(self):
        self.collector.dispatch({'op':'state'})
        self.collector.after_disconnect()
        self.assertFalse(self.collector.closing)
        self.collector.dispatch({'op':'window-opened'})
        self.collector.after_disconnect()
        self.assertTrue(self.collector.closed.wait(10),'Diagnostic: detached disabled window not stopped')

    def test_invalid_control_query_returns_public_error_without_killing_pipe(self):
        name='control-'+uuid.uuid4().hex
        server=reader.PipeServer(name,reader.current_sid(),self.collector)
        thread=threading.Thread(target=server.serve)
        thread.start();server.ready.wait()
        client=reader.PipeClient(name)
        try:
            with self.assertRaises(reader.ReaderError) as raised:
                client.request({'op':'query','body':{'queries':[{'kind':'not-a-kind'}]}})
            self.assertEqual(raised.exception.state,'invalid-query')
            self.assertEqual(client.request({'op':'state'})['state'],'disabled')
        finally:
            client.close();server.stop();thread.join()

    def test_unexpected_command_failure_resolves_current_waiter_before_worker_exit(self):
        original = self.collector._execute
        def broken(store, op, body):
            if op == 'state':
                raise LookupError('synthetic internal defect')
            return original(store,op,body)
        with patch.object(self.collector,'_execute',side_effect=broken):
            future = self.collector.submit('state')
            self.assertTrue(self.collector.closed.wait(10), 'Diagnostic: worker exit not observed')
            self.assertTrue(future.done(), 'The dequeued request must not hang forever')
            with self.assertRaises(reader.ReaderError):
                future.result()

    def test_unauthorized_origins_headers_paths_and_injection_fail(self):
        session = self.collector.session()
        for headers in (
            {'Content-Type':'application/json'},
            {'Authorization':'Bearer '+session['token'], 'Origin':'https://foreign.invalid','Content-Type':'application/json'},
            {'Authorization':'Bearer '+session['token'], 'Origin':session['origin'],'Content-Type':'text/plain'},
        ):
            self.assertEqual(self.post('/api/query', {}, headers)[0], 403)
        self.assertEqual(self.post('/api/query?token='+session['token'], {})[0], 404)
        self.assertEqual(self.post('/api/query', {'queries':[{'kind':'traffic; DROP TABLE traffic'}]})[0], 400)

    def test_duplicate_owner_and_deleted_history_catchup(self):
        other = runtime.Collector(self.home, self.client, instance=self.collector.instance)
        try:
            with self.assertRaises(runtime.RuntimeError):
                other.start()
        finally:
            other.close()
        self.collector.command('configure', {'traffic':True})
        self.collector.command('refresh')
        self.collector.command('delete', {'kind':'traffic','start':'2026-10-07T00:00:00Z','end':'2026-10-08T00:00:00Z'})
        self.collector.command('refresh')
        self.assertEqual(self.query()[1]['results'][0]['data']['total_count'], 0)

    def test_memory_credentials_and_diagnostics_never_export_token(self):
        token = 'synthetic-read-' + uuid.uuid4().hex
        result = self.collector.command('credential', {'token':token,'confirm_read_only':True,'persist':False})
        self.assertEqual(result['storage'], 'process-memory')
        self.collector.command('configure', {'traffic':True})
        self.collector.command('refresh')
        self.assertNotIn(token, json.dumps(self.post('/api/state', {})[1]))
        for path in self.home.glob('*.json'):
            self.assertNotIn(token, path.read_text())
        self.assertNotIn(token, json.dumps(self.query()[1]))

    def test_idle_unfinished_http_peer_is_closed_by_explicit_shutdown(self):
        import socket
        connection = socket.create_connection(('127.0.0.1',self.collector.session()['port']))
        try:
            connection.sendall(b'POST /api/query HTTP/1.1\r\n')
            self.collector.close()
            self.assertEqual(connection.recv(1), b'')
        finally:
            connection.close()

    def test_pause_backpressure_and_query_yield_at_committed_slice_boundary(self):
        entered, release = threading.Event(), threading.Event()
        original = self.server.source
        class GatedSource:
            catalogs = 0
            reads = 0
            def dispatch(source, request):
                if request.get('op') == 'catalog':
                    source.catalogs += 1
                if request.get('op') == 'traffic':
                    source.reads += 1
                    if source.reads == 1:
                        entered.set()
                        release.wait()
                return original.dispatch(request)
        gate = GatedSource()
        self.server.source = gate
        try:
            self.collector.command('configure', {'traffic':True})
            self.assertTrue(entered.wait(10), 'Diagnostic: source read did not begin')
            paused = self.collector.submit('pause')
            queued = [self.collector.submit('state') for _ in range(31)]
            with self.assertRaises(runtime.RuntimeError):
                self.collector.submit('state')
            release.set()
            self.assertEqual(paused.result()['state'],'paused')
            self.assertTrue(all(f.result()['state']=='paused' for f in queued))
            self.assertEqual(gate.catalogs,1)
            self.assertEqual(gate.reads,1)  # Pause prevented the next source read.
            self.assertEqual(self.query()[0],200)
        finally:
            release.set()

    def test_real_sqlite_full_rolls_back_then_restart_recovers(self):
        self.collector.close()
        large_app = test_glasswire.string(6, 'C:\\Synthetic\\'+('a'*16000)+'.exe')
        with closing(sqlite3.connect(self.main)) as db:
            db.execute('UPDATE applications SET data=?',(large_app,))
            db.commit()
        original = history.History
        def limited(*args,**kwargs):
            store = original(*args,**kwargs)
            pages = store.db.execute('PRAGMA page_count').fetchone()[0]
            store.db.execute('PRAGMA max_page_count='+str(pages))
            return store
        with patch.object(history,'History',side_effect=limited):
            self.collector = runtime.Collector(self.home,self.client,now=lambda:'2026-10-08T00:00:00Z')
            self.collector.start()
            try:
                self.collector.command('configure',{'traffic':True})
                state = self.collector.command('refresh')
                self.assertEqual(state['state'],'write-error')
                self.assertEqual(self.query()[1]['results'][0]['data']['total_count'],0)
            finally:
                self.collector.close()
        self.collector = runtime.Collector(self.home,self.client,now=lambda:'2026-10-08T00:00:00Z')
        self.collector.start()
        self.addCleanup(self.collector.close)
        self.collector.command('refresh')
        self.assertEqual(self.query()[1]['results'][0]['data']['total_count'],1)

    def test_native_reader_outage_preserves_facts_and_recovers(self):
        self.collector.command('configure',{'traffic':True})
        self.collector.command('refresh')
        self.server.stop()
        self.reader_thread.join()
        self.assertNotIn('last_success_utc',self.collector.command('refresh')['sources']['traffic'])
        self.assertEqual(self.query()[1]['results'][0]['data']['total_count'],1)
        name = self.client.name.removeprefix('\\\\.\\pipe\\Darkaxt.TailD.')
        self.server = reader.PipeServer(name,reader.current_sid(),reader.GlassWireSource(self.root))
        self.reader_thread = threading.Thread(target=self.server.serve)
        self.reader_thread.start()
        self.assertTrue(self.server.ready.wait(10),'Diagnostic: restarted reader not ready')
        self.collector.command('refresh')
        self.assertEqual(self.query()[1]['results'][0]['data']['total_count'],1)

    def test_http_429_is_not_retried_by_manual_refresh_or_resume(self):
        from http.server import BaseHTTPRequestHandler,HTTPServer
        class Provider(BaseHTTPRequestHandler):
            reads = 0
            def do_GET(self):
                Provider.reads += 1
                self.send_response(429)
                self.send_header('Retry-After','120')
                self.send_header('Content-Length','0')
                self.end_headers()
            def log_message(self,*args):
                pass
        provider = HTTPServer(('127.0.0.1',0),Provider)
        worker = threading.Thread(target=provider.serve_forever)
        worker.start()
        original = controld._read
        def local_read(url,token,organization=None):
            return original('http://127.0.0.1:'+str(provider.server_port)+'/synthetic-read',token,organization)
        try:
            with patch.object(controld,'_read',side_effect=local_read):
                self.collector.command('credential',{'token':'synthetic-read-token','confirm_read_only':True,'persist':False})
                self.collector.command('configure',{'dns':True,'provider':{'account_scope':'synthetic','endpoint':'synthetic',
                    'account_type':'personal','instance':'synthetic'}})
                state = self.collector.command('refresh')
                self.assertEqual(state['sources']['dns']['state'],'rate-limited')
                self.collector.command('resume')
                self.collector.command('refresh')
                self.assertEqual(Provider.reads,1)
                self.collector.close()
                self.collector = runtime.Collector(self.home,self.client,now=lambda:'2026-10-08T00:00:00Z')
                self.collector.start()
                self.addCleanup(self.collector.close)
                self.collector.command('credential',{'token':'synthetic-read-token','confirm_read_only':True,'persist':False})
                self.collector.command('refresh')
                self.assertEqual(Provider.reads,1,'Restart must not bypass the provider retry-after window')
        finally:
            provider.shutdown()
            worker.join()
            provider.server_close()

    def test_http_provider_denial_and_recovery_preserve_committed_dns_history(self):
        from http.server import BaseHTTPRequestHandler,HTTPServer
        from urllib.parse import urlsplit,parse_qs
        class Provider(BaseHTTPRequestHandler):
            allowed=False
            def do_GET(self):
                if not Provider.allowed:
                    self.send_response(401);self.send_header('Content-Length','0');self.end_headers();return
                parsed=urlsplit(self.path)
                if '/activity-log/csv' in parsed.path:
                    query=parse_qs(parsed.query)
                    text='timestamp,endpointId,question,action\n'
                    stamp='2026-10-07T16:36:41Z'
                    if history.instant(query['startTime'][0])<=history.instant(stamp)<=history.instant(query['endTime'][0]):
                        text+=stamp+',synthetic,example.invalid,unknown\n'
                    body=text.encode()
                else:
                    body=b'{"success":true,"body":{}}'
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        provider=HTTPServer(('127.0.0.1',0),Provider)
        worker=threading.Thread(target=provider.serve_forever);worker.start()
        original=controld._read
        def local_read(url,token,organization=None):
            parsed=urlsplit(url)
            return original('http://127.0.0.1:'+str(provider.server_port)+parsed.path+('?' + parsed.query if parsed.query else ''),token,organization)
        try:
            with patch.object(controld,'_read',side_effect=local_read):
                self.collector.command('credential',{'token':'synthetic-read-token','confirm_read_only':True,'persist':False})
                self.collector.command('configure',{'dns':True,'provider':{'account_scope':'synthetic','endpoint':'synthetic',
                    'account_type':'personal','instance':'synthetic'}})
                denied=self.collector.command('refresh')
                self.assertEqual(denied['sources']['dns']['state'],'denied')
                self.collector.command('pause');Provider.allowed=True
                self.collector.command('resume');self.collector.command('refresh');self.collector.command('pause')
                query={'kind':'dns','view':'facts','start':'2026-10-07T00:00:00Z','end':'2026-10-08T00:00:00Z','limit':10}
                before=self.collector.command('query',{'queries':[query]})['results'][0]['data']['total_count']
                self.assertEqual(before,1)
                Provider.allowed=False;self.collector.command('resume')
                self.assertEqual(self.collector.command('refresh')['sources']['dns']['state'],'denied')
                self.assertEqual(self.collector.command('query',{'queries':[query]})['results'][0]['data']['total_count'],before)
        finally:
            provider.shutdown();worker.join();provider.server_close()

    def test_bounded_dns_backfill_continues_without_false_gap_or_duplicate(self):
        store = history.History(self.root/'pending-history',now='2026-10-08T00:00:00Z')
        start,end = '2026-10-07T16:36:40Z','2026-10-07T16:36:48Z'
        calls = []
        def fetch(left,right):
            calls.append((left,right))
            a,b = history.bounds(left,right)
            truncated = b-a > 1000000
            rows = [] if truncated else [{'source':'controld-activity-csv','raw':{
                'timestamp':history.utc(a+500000),'endpointId':'synthetic','question':'example.invalid','action':'unknown'}}]
            return {'source':'controld-activity-csv','collected_at_utc':'2026-10-08T00:00:00Z',
                'query_window':{'start_inclusive':left,'end_inclusive':right},'endpoint_id':'synthetic',
                'truncated':truncated,'rows':rows}
        try:
            pending = None
            for _ in range(8):  # Diagnostic census bound, not an execution timer.
                before = len(calls)
                result = ingestion.dns_windows(store,'synthetic','synthetic',start,end,fetch,
                    max_slices=3,defer_budget=True,resume_pending=pending)
                self.assertLessEqual(len(calls)-before,3)
                pending = result['pending_windows']
                if not pending:
                    break
            self.assertEqual(pending,[])
            self.assertEqual(store.query('dns',start,end)['row_count'],8)
            ingestion.dns_windows(store,'synthetic','synthetic',start,end,fetch,max_slices=16)
            self.assertEqual(store.query('dns',start,end)['row_count'],8)
            self.assertEqual(store.db.execute("SELECT count(*) FROM runs WHERE state='irreducibly-capped'").fetchone()[0],0)
        finally:
            store.close()

    def test_native_resume_subscription_is_hidden_and_unregisters_on_stop(self):
        import win32con
        import win32gui
        self.assertTrue(hasattr(self.collector,'lifecycle'),'Windows lifecycle event subscription missing')
        listener = self.collector.lifecycle
        self.assertEqual(listener.status()['state'],'subscribed')
        self.assertFalse(win32gui.IsWindowVisible(listener.hwnd))
        before = listener.status()['resume_events']
        # An actual message delivered to our native window is diagnostic wiring
        # evidence, not a claim that the physical machine slept/woke.
        win32gui.SendMessage(listener.hwnd,win32con.WM_POWERBROADCAST,18,0)
        self.assertEqual(listener.status()['resume_events'],before+1)
        self.assertEqual(self.collector.command('state')['state'],'disabled')
        handle = listener.hwnd
        self.collector.close()
        self.assertFalse(win32gui.IsWindow(handle))
        self.assertEqual(listener.status()['state'],'stopped')


if __name__ == '__main__':
    unittest.main()
