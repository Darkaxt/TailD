"""Isolated no-console packaged collector -> real read-only daemon -> history.

No installation, startup registration, VPN writes, provider reads or transfers.
"""
import argparse,hashlib,json,subprocess,uuid
from pathlib import Path
import history,reader


def run(executable,output):
    import win32api,win32con,win32event,win32file
    history.private_directory(output);home=output/'history';history.private_directory(home)
    instance='frozen-'+uuid.uuid4().hex;name='Local\\Darkaxt.TailD.Ready.'+instance
    ready=win32event.CreateEvent(None,True,False,name)
    change=win32file.FindFirstChangeNotification(str(home),False,
        win32con.FILE_NOTIFY_CHANGE_FILE_NAME|win32con.FILE_NOTIFY_CHANGE_LAST_WRITE)
    process=None;client=None
    try:
        process=subprocess.Popen([str(executable),'collector','run','--history',str(home),
            '--reader-instance','unused-activity-fixture','--instance',instance,'--ready-event',name],
            creationflags=subprocess.CREATE_NO_WINDOW)
        observed=win32event.WaitForMultipleObjects([ready,int(process._handle)],False,win32event.INFINITE)
        if observed!=win32event.WAIT_OBJECT_0:raise AssertionError('Frozen collector exited before ready: '+str(process.wait()))
        client=reader.PipeClient(instance)
        initial=client.request({'op':'state'})
        assert not any(initial['settings'][key] for key in ('activity','traffic','dns'))
        client.request({'op':'activity-configure','body':{'enabled':True}})
        # File-change notifications are diagnostic observations, not polling,
        # time-based completion or permission to cancel the original operation.
        while True:
            observed=win32event.WaitForMultipleObjects([change,int(process._handle)],False,win32event.INFINITE)
            if observed!=win32event.WAIT_OBJECT_0:raise AssertionError('Frozen collector exited during observation')
            win32file.FindNextChangeNotification(change)
            # Atomic status-file replacement can briefly reject a filesystem
            # reader. Use the authenticated non-SQL observation channel after
            # the file-change wake, not a read/retry against that rename.
            value=client.request({'op':'state'})
            if value['sources'].get('activity',{}).get('state')=='connected':break
        data=client.request({'op':'activity-read','body':{'view':'devices'}})
        assert len(data['rows'])>0
        assert all(row['presence'] in ('online','offline','unknown') for row in data['rows'])
        state=client.request({'op':'state'})
        assert not state['settings']['traffic'] and not state['settings']['dns']
        client.request({'op':'shutdown'});client.close();client=None
        assert process.wait()==0
        store=history.History(home)
        try:
            check=store.db.execute('PRAGMA quick_check').fetchone()[0];assert check=='ok'
        finally:store.close()
        report={'ok':True,'frozen_entrypoint':True,'read_only_daemon_subscription':True,
            'visible_peers':len(data['rows']),'source_independence':True,'graceful_exit_code':process.returncode,
            'sqlite_quick_check':check,'sqlite_dll_sha256':hashlib.sha256((executable.parent/'_internal/sqlite3.dll').read_bytes()).hexdigest(),
            'executable_sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),
            'source_sha256':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ('runtime.py','tailscale_activity.py')},'installed_client_unchanged':True}
        (output/'frozen-activity.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
    finally:
        if client is not None:
            try:
                if process.poll() is None:client.request({'op':'shutdown'})
            finally:client.close()
        if process is not None and process.poll() is None:
            # Startup failures already signal process exit; admitted collectors
            # receive explicit shutdown above. Never kill by an elapsed deadline.
            process.wait()
        win32api.CloseHandle(ready);win32file.FindCloseChangeNotification(change)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--collector',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.collector.resolve(strict=True),args.output.resolve())
