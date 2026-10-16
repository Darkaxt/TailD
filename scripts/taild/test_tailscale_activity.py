"""Daemon protocol metadata -> real private SQLite; synthetic transfers only."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
import uuid
import threading
from unittest.mock import patch
import history

activity=__import__('tailscale_activity') if importlib.util.find_spec('tailscale_activity') else None
NOW='2026-10-16T12:00:00Z'
LATER='2026-10-16T12:01:00Z'


class ActivityTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(activity,'Tailscale-native tracking is missing')
        root=Path(__import__('os').environ['TAILD_PACKAGE_TEST_OUTPUT'])/'activity'/uuid.uuid4().hex
        root.parent.mkdir(parents=True,exist_ok=True)
        self.home=root
        self.store=history.History(root,now=NOW)
        self.addCleanup(self.store.close)
        self.tracker=activity.Tracker(self.store)

    def snapshot(self,profile='a',online=True,**extra):
        return self.tracker.snapshot(profile,{'BackendState':'Running','ExitNodeStatus':{'ID':'exit-a'},
            'Peer':{'key':{'ID':'peer-a','HostName':'Phone','OS':'android','Online':online,
            'PublicKey':'PRIVATE','TailscaleIPs':['100.64.0.1']}}},
            {'Configured':True,'Applied':True,'CaptivePortal':False,'Endpoint':'https://secret.invalid'},NOW,**extra)

    def view(self,kind='events',profile='a'):
        return activity.read(self.store,{'view':kind,'profile':profile},LATER)

    def test_presence_baseline_changes_gaps_and_profile_isolation(self):
        self.snapshot();self.snapshot()
        self.snapshot(online=False)
        self.snapshot(profile='b',online=True)
        self.assertEqual(len(self.view('devices')['rows']),1)
        events=self.view()['rows']
        self.assertEqual(sum(e['type']=='peer-presence' for e in events),1)
        self.tracker.gap('a','disconnected',LATER)
        self.assertEqual(self.view('devices')['rows'][0]['presence'],'unknown')
        self.snapshot(online=True)
        self.assertEqual(sum(e['type']=='peer-presence' for e in self.view()['rows']),1,
            'Re-observation after a gap must be a baseline, not fabricated uptime')
        raw=json.dumps(self.view('devices'))
        self.assertNotIn('PRIVATE',raw);self.assertNotIn('PublicKey',raw)

    def test_transfers_explicit_completion_replay_restart_and_missing_not_success(self):
        outgoing={'ID':'transfer-a','PeerID':'peer-a','Name':r'C:\private\report.txt',
            'Started':NOW,'DeclaredSize':20,'Sent':10,'Finished':False,'Succeeded':False}
        self.tracker.notify('a',{'OutgoingFiles':[outgoing]},NOW)
        self.tracker.notify('a',{'OutgoingFiles':None},LATER)
        self.assertEqual(self.view('transfers')['rows'][0]['result'],'in-progress')
        self.tracker.notify('a',{'OutgoingFiles':[{'ID':'transfer-a','Name':'invalid'}]},LATER)
        self.assertEqual(self.view('transfers')['rows'][0]['result'],'in-progress')
        self.tracker.notify('a',{'OutgoingFiles':[]},LATER)
        self.assertEqual(self.view('transfers')['rows'][0]['result'],'unknown')
        outgoing.update(Finished=True,Succeeded=True,Sent=20)
        self.tracker.notify('a',{'OutgoingFiles':[outgoing]},LATER)
        activity.Tracker(self.store).notify('a',{'OutgoingFiles':[outgoing]},LATER)
        rows=self.view('transfers')['rows']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['result'],'sent')
        self.assertEqual(rows[0]['name'],'report.txt')
        incoming={'Name':'received.txt','Started':NOW,'DeclaredSize':-1,'Received':7,'Done':True,
            'PartialPath':'PRIVATE','FinalPath':'PRIVATE'}
        self.tracker.notify('a',{'IncomingFiles':[incoming]},LATER)
        rows=self.view('transfers')['rows']
        self.assertIn('received-by-daemon',[r['result'] for r in rows])
        self.assertNotIn('PRIVATE',json.dumps(rows));self.assertNotIn('C:',json.dumps(rows))

    def test_offline_snapshot_is_not_activity_or_last_online_contact(self):
        status={'Peer':{'key':{'ID':'offline','HostName':'Tablet','Online':False,
            'LastSeen':'2026-10-16T13:00:00+03:00'}}}
        self.tracker.snapshot('a',status,{},NOW)
        self.tracker.snapshot('a',status,{},LATER)
        row=self.view('devices')['rows'][0]
        self.assertEqual(row.get('last_seen'),'2026-10-16T10:00:00.000000000Z')
        self.assertNotEqual(row['last_seen'],row['observed_at'])
        self.assertEqual(self.view()['rows'],[],'An initial offline status is not device activity')
        initial=activity.read(self.store,{'view':'events','include_baselines':True},LATER)
        self.assertEqual(sum(e['type']=='peer-baseline' for e in initial['rows']),1)
        status['Peer']['key'].update(Online=True)
        self.tracker.snapshot('a',status,{},LATER)
        self.assertIsNone(self.view('devices')['rows'][0].get('last_seen'))
        events=self.view()['rows']
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['type'],'peer-presence')
        self.assertEqual(events[0]['value']['from'],'offline')
        self.assertEqual(events[0]['value']['to'],'online')
        for value in (None,'invalid','0001-01-01T00:00:00Z'):
            status['Peer']['key'].update(Online=False,LastSeen=value)
            self.tracker.snapshot('a',status,{},LATER)
            self.assertIsNone(self.view('devices')['rows'][0].get('last_seen'))

    def test_baselines_do_not_crowd_real_changes_out_of_the_default_bounded_view(self):
        self.snapshot();self.snapshot(online=False)
        with self.store.transaction():
            for i in range(220):self.tracker._event('a','peer-baseline',{'presence':'offline','id':str(i)},LATER)
        rows=self.view()['rows']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['type'],'peer-presence')
        self.assertTrue(activity.read(self.store,{'view':'events','include_baselines':True},LATER)['truncated'])
        with self.assertRaises(ValueError):activity.read(self.store,{'include_baselines':1},LATER)

    def test_failure_health_and_delete_replay_suppression(self):
        self.snapshot(health={'Warnings':{'local-dns-encrypted-recovery':{'Text':'PRIVATE'}}})
        self.snapshot(health={'Warnings':{}})
        self.assertTrue(any(e['type']=='resolver' for e in self.view()['rows']))
        self.snapshot(health={'Warnings':None})
        self.assertIs(self.tracker._get(history.digest(['activity-state','a','resolver']))['fallback'],False)
        failed={'ID':'failed','Name':'bad.txt','Started':NOW,'DeclaredSize':1,'Sent':0,
            'Finished':True,'Succeeded':False}
        self.tracker.notify('a',{'OutgoingFiles':[failed]},NOW)
        self.assertEqual(self.view('transfers')['rows'][0]['result'],'failed')
        activity.delete(self.store,{'confirm':True},LATER)
        activity.Tracker(self.store).notify('a',{'OutgoingFiles':[failed]},LATER)
        self.assertEqual(self.view('transfers')['rows'],[])
        self.store.now=history.instant('2026-10-25T12:00:00Z');self.store.cleanup()
        self.assertEqual(self.view()['rows'],[])
        with self.assertRaises(ValueError):activity.delete(self.store,{'confirm':1},LATER)

    def test_malformed_private_inputs_cannot_be_persisted(self):
        self.tracker.notify('a',{'OutgoingFiles':[{'Name':'SECRET','Sent':True}],
            'BrowseToURL':'PRIVATE','Prefs':{'Persist':'PRIVATE'}},NOW)
        self.assertEqual(self.view('transfers')['rows'],[])
        self.tracker.snapshot('a',{'ExitNodeStatus':['bad'],'Peer':{'a':{'ID':'peer','HostName':'\ud800'}}},{},NOW)
        with self.assertRaises(ValueError):activity.read(self.store,{'path':'anything'},NOW)

    def test_activity_progress_does_not_scan_or_expire_other_fact_sources(self):
        statements=[];self.store.db.set_trace_callback(statements.append)
        self.snapshot()
        self.assertFalse(any('DELETE FROM traffic' in sql or 'DELETE FROM applications' in sql for sql in statements),
            'Frequent IPN/file progress must not run whole-history orphan/traffic maintenance')

    def test_go_transfer_offset_and_nanoseconds_are_normalized_without_identity_loss(self):
        value={'Name':'offset.txt','Started':'2026-10-16T15:00:00.123456789+03:00',
            'DeclaredSize':1,'Received':1,'Done':True}
        self.tracker.notify('a',{'IncomingFiles':[value]},LATER)
        rows=self.view('transfers')['rows']
        self.assertEqual(len(rows),1,'Go local-time timestamps must not be discarded')
        self.assertEqual(rows[0]['started_at'],'2026-10-16T12:00:00.123456789Z')
        value['Started']='2026-10-16T12:00:00.123456789Z'
        self.tracker.notify('a',{'IncomingFiles':[value]},LATER)
        self.assertEqual(len(self.view('transfers')['rows']),1)

    @unittest.skipUnless(os.name=='nt','Windows overlapped pipe boundary')
    def test_pending_named_pipe_read_cancels_and_settles_before_exit(self):
        import win32pipe,win32file,win32con,win32event
        name=r'\\.\pipe\TailD.activity-fixture-'+uuid.uuid4().hex
        server=win32pipe.CreateNamedPipe(name,win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_BYTE|win32pipe.PIPE_WAIT,1,4096,4096,0,None)
        pending,release=threading.Event(),threading.Event();errors=[]
        def serve():
            try:
                win32pipe.ConnectNamedPipe(server,None);win32file.ReadFile(server,4096)
                win32file.WriteFile(server,b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n')
                release.wait()
            finally:server.Close()
        stream=activity.Stream();original=win32file.ReadFile
        def read(handle,count,ov=None):
            value=original(handle,count,ov)
            if threading.current_thread().name=='activity-cancellation' and value[0]==997:pending.set()
            return value
        def consume():
            try:
                with stream.request(activity.WATCH) as response:response.readline()
            except reader.ReaderError as error:errors.append(error.state)
        import reader
        serving=threading.Thread(target=serve);worker=threading.Thread(target=consume,name='activity-cancellation')
        try:
            with patch.object(activity,'PIPE',name),patch.object(win32file,'ReadFile',read):
                serving.start();worker.start();pending.wait();stream.cancel();worker.join()
                self.assertEqual(errors,['stopped']);self.assertFalse(worker.is_alive())
        finally:
            release.set();serving.join()
            stream.stop.Close();stream.stop=None
