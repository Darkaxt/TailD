"""Native owner-authenticated reader -> real SQLite -> owned history diagnostics."""
from contextlib import closing
import importlib.util
import os
from pathlib import Path
import sqlite3
import threading
import unittest
import uuid

import glasswire
import history
import ingestion
import test_glasswire

reader = __import__('reader') if importlib.util.find_spec('reader') else None
START = '2026-10-07T16:36:40Z'
END = '2026-10-07T16:36:43Z'


@unittest.skipUnless(os.name == 'nt', 'Windows native named-pipe boundary')
class ReaderTest(unittest.TestCase):
    add_row = test_glasswire.GlassWireTest.add_row

    def setUp(self):
        self.assertIsNotNone(reader, 'Authenticated read-only GlassWire reader is missing')
        test_glasswire.GlassWireTest.setUp(self)
        self.writer.close()
        (self.root/'stats').mkdir()
        self.stats = self.stats.replace(self.root/'stats'/self.stats.name)
        with closing(sqlite3.connect(self.main)) as db:
            db.execute('CREATE TABLE stats_databases(filename BLOB,timestamp INTEGER,expire_time INTEGER,scale INTEGER)')
            db.execute('INSERT INTO stats_databases VALUES(?,1791331200,1791504000,1)', (self.stats.name.encode(),))
            db.commit()
        self.name = 'test-' + uuid.uuid4().hex
        self.server = reader.PipeServer(self.name, reader.current_sid(), reader.GlassWireSource(self.root))
        self.errors = []
        def serve():
            try:
                self.server.serve()
            except BaseException as error:
                self.errors.append(error)
        self.thread = threading.Thread(target=serve)
        self.thread.start()
        self.addCleanup(self.finish)
        self.assertTrue(self.server.ready.wait(10), 'Diagnostic: pipe did not become ready')
        self.client = reader.PipeClient(self.name)
        self.addCleanup(self.client.close)

    def finish(self):
        self.server.stop()
        self.thread.join()
        self.assertEqual(self.errors, [])

    def test_complete_reader_ingest_query_restart_workflow(self):
        store = history.History(self.root/'history', now='2026-10-08T00:00:00Z')
        try:
            result = ingestion.traffic_window(store, 'synthetic', START, END, reader=self.client)
            self.assertEqual(result['slice_attempts'], 1)
            self.assertEqual(store.query('traffic', START, END)['inbound_bytes'], 100)
        finally:
            store.close()
        store = history.History(self.root/'history', now='2026-10-08T00:00:00Z')
        try:
            ingestion.traffic_window(store, 'synthetic', START, END, reader=self.client)
            self.assertEqual(store.query('traffic', START, END)['row_count'], 1)
        finally:
            store.close()

    def test_only_catalogue_bound_fixed_operations(self):
        catalog = self.client.discover()
        self.assertEqual(len(catalog['databases']), 1)
        invalid = [
            {'op':'shell', 'command':'whoami'},
            {'op':'catalog', 'path':str(self.root)},
            {'op':'traffic','database':str(self.stats),'start':START,'end':END,'limit':10},
            {'op':'traffic','database':'0'*64,'start':START,'end':END,'limit':True},
            {'op':'traffic','database':'0'*64,'start':START,'end':'2026-10-09T00:00:00Z','limit':10},
        ]
        for request in invalid:
            with self.subTest(op=request['op']), self.assertRaises(reader.ReaderError):
                self.client.request(request)
        self.assertEqual(self.client.discover()['version'], 'explicit-override-version-unverified')

    def test_stop_cancels_pending_connect_without_deadline(self):
        self.server.stop()
        self.thread.join()
        self.assertFalse(self.thread.is_alive())

    def test_wrong_owner_identity_is_denied_after_native_authentication(self):
        self.server.owner_sid = 'S-1-5-19'
        with self.assertRaises(reader.ReaderError):
            self.client.discover()

    def test_collision_cannot_replace_existing_pipe(self):
        other = reader.PipeServer(self.name, reader.current_sid(), reader.GlassWireSource(self.root))
        try:
            with self.assertRaises(reader.ReaderError):
                other.serve()
        finally:
            other.close()


class ProtocolTest(unittest.TestCase):
    def test_duplicate_keys_nonfinite_and_resource_bounds_fail_closed(self):
        self.assertIsNotNone(reader, 'Bounded reader protocol is missing')
        for raw in (b'{"op":"catalog","op":"traffic"}', b'{"op":NaN}',
                    b'['*40 + b'0' + b']'*40, b'{} '*40000):
            with self.subTest(size=len(raw)), self.assertRaises(reader.ReaderError):
                reader.decode_message(raw)


if __name__ == '__main__':
    unittest.main()
