"""Portable writer/acquisition contracts, not owner-token or installed IPC proof.

The actual unelevated Windows lifecycle/pipe boundary remains in test_runtime.
These same concurrency regressions also run on the hosted Linux check job.
"""
from contextlib import closing
from types import SimpleNamespace
import sqlite3
import threading
import unittest
import uuid
from unittest.mock import patch

import glasswire
import reader
import runtime
import test_glasswire
import test_runtime


class SchedulingTest(unittest.TestCase):
    add_row=test_glasswire.GlassWireTest.add_row
    test_controld_commits_while_glasswire_read_is_held=(
        test_runtime.RuntimeTest.test_controld_commits_while_glasswire_read_is_held)
    test_glasswire_commits_while_controld_read_is_held_and_stop_joins_both=(
        test_runtime.RuntimeTest.test_glasswire_commits_while_controld_read_is_held_and_stop_joins_both)

    def test_caller_queue_still_has_bounded_admission(self):
        with self.collector.condition:
            queued=[self.collector.submit('state') for _ in range(32)]
            with self.assertRaisesRegex(runtime.RuntimeError,'backpressure'):
                self.collector.submit('state')
        self.assertTrue(all(future.result()['state']=='disabled' for future in queued))

    def test_pause_before_acquisition_entry_admits_no_catalog_read(self):
        entered,release=threading.Event(),threading.Event()
        original=self.collector._acquire;source=self.server.source;catalogs=[]
        class Source:
            def dispatch(inner,request):
                if request.get('op')=='catalog':catalogs.append(request)
                return source.dispatch(request)
        self.server.source=Source()
        def held(*args,**kwargs):
            entered.set();release.wait();return original(*args,**kwargs)
        try:
            with patch.object(self.collector,'_acquire',side_effect=held):
                self.collector.command('configure',{'traffic':True})
                self.assertTrue(entered.wait(10),'Diagnostic: acquisition not admitted')
                self.collector.command('pause');release.set();self.collector.close()
                self.assertEqual(catalogs,[],'Paused acquisition still read the GlassWire catalog')
        finally:release.set()

    def test_resume_starts_a_fresh_recent_pass_after_the_inflight_read(self):
        entered,release,second=threading.Event(),threading.Event(),threading.Event()
        source=self.server.source;windows=[]
        class Source:
            def dispatch(inner,request):
                if request.get('op')=='traffic':
                    windows.append((request['start'],request['end']))
                    if len(windows)==1:entered.set();release.wait()
                    elif len(windows)==2:second.set()
                return source.dispatch(request)
        self.server.source=Source()
        try:
            self.collector.command('configure',{'traffic':True,'traffic_seconds':86400})
            self.assertTrue(entered.wait(10),'Diagnostic: first source read not entered')
            self.collector.command('pause');self.collector.command('resume');release.set()
            self.assertTrue(second.wait(10),'Resume lost its acquisition opportunity')
            self.collector.command('pause');self.collector.close()
            self.assertEqual(windows[1],windows[0],'Resume continued old backfill instead of a fresh recent pass')
        finally:release.set()

    def setUp(self):
        isolated=patch.object(runtime.live_dns,'Stream',test_runtime.IsolatedLiveStream)
        isolated.start();self.addCleanup(isolated.stop)
        test_glasswire.GlassWireTest.setUp(self)
        self.writer.close();(self.root/'stats').mkdir()
        self.stats=self.stats.replace(self.root/'stats'/self.stats.name)
        with closing(sqlite3.connect(self.main)) as db:
            db.execute('CREATE TABLE stats_databases(filename BLOB,timestamp INTEGER,expire_time INTEGER,scale INTEGER)')
            db.execute('INSERT INTO stats_databases VALUES(?,1791331200,1791504000,1)',(self.stats.name.encode(),))
            db.commit()
        self.server=SimpleNamespace(source=reader.GlassWireSource(self.root))
        server=self.server
        class Source:
            def discover(inner,directory):
                inner.catalog=server.source.dispatch({'op':'catalog'})
                return inner.catalog
            def physical_identity(inner,path):return glasswire.physical_identity(path)
            def read_traffic(inner,path,main,left,right,limit):
                entry=next(item for item in inner.catalog['databases'] if str(item['path'])==str(path))
                return server.source.dispatch({'op':'traffic','database':entry['reader_id'],
                    'start':left,'end':right,'limit':limit})
        self.home=self.root/'history'
        self.collector=runtime.Collector(self.home,Source(),now=lambda:'2026-10-08T00:00:00Z',
            instance='scheduling-'+uuid.uuid4().hex)
        # Exercise the actual dispatcher without pretending this unit harness
        # passes Windows owner/elevation checks or registers a native listener.
        self.collector.thread=threading.Thread(target=self.collector._run)
        self.collector.thread.start();self.collector.ready.wait()
        self.addCleanup(self.collector.close)
        self.assertIsNone(self.collector.start_error)


if __name__=='__main__':unittest.main()
