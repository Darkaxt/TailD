"""Fixed TailD reader/package integration for the Inno Setup installer.

Never modifies the Tailscale service, connectivity binaries, node keys, provider
policies or user collection settings. No remote command surface or arbitrary SQL.
"""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import sys

import package_manifest as manifest

SERVICE='TailDReadOnlyReader'
UNINSTALL_KEY=r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{04905050-B54D-4D29-9880-39F10B3BCA7E}_is1'


def notification_mask(state):
    # SCM immediately notifies an already-current state. Exclude it to wait
    # for a real transition rather than an endless sequence of immediate APCs.
    return 0x7f & ~(1 << (state-1))


def known_folder(identifier):
    output=ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None,identifier,None,0,output)!=0:
        raise manifest.PackageError('windows-folder-unavailable')
    return Path(output.value)


def app_directory():return known_folder(0x26)/'Tailscale'/'TailD'


def service_wait(handle,target):
    """SCM status notification/APC, not polling or elapsed-time cancellation."""
    import win32api,win32event,win32service
    class Status(ctypes.Structure):
        _fields_=[(name,wintypes.DWORD) for name in ('type','state','accepted','win32_exit','service_exit','checkpoint','wait_hint','pid','flags')]
    callback_type=ctypes.WINFUNCTYPE(None,ctypes.c_void_p)
    class Notification(ctypes.Structure):
        _fields_=[('version',wintypes.DWORD),('callback',callback_type),('context',ctypes.c_void_p),
            ('error',wintypes.DWORD),('status',Status),('triggered',wintypes.DWORD),('names',wintypes.LPWSTR)]
    api=ctypes.WinDLL('advapi32',use_last_error=True)
    api.NotifyServiceStatusChangeW.argtypes=[wintypes.HANDLE,wintypes.DWORD,ctypes.POINTER(Notification)]
    api.NotifyServiceStatusChangeW.restype=wintypes.DWORD
    event=win32event.CreateEvent(None,True,False,None)
    try:
        callback=callback_type(lambda _:win32event.SetEvent(event))
        notification=Notification(version=2,callback=callback)
        while True:
            status=win32service.QueryServiceStatusEx(handle)
            if status['CurrentState']==target:return status
            if target==win32service.SERVICE_RUNNING and status['CurrentState']==win32service.SERVICE_STOPPED:
                raise manifest.PackageError('reader-start-failed')
            # Subscribe to all actual changes, so an unsuccessful start is also
            # observed. The notification storage stays alive through the APC.
            win32event.ResetEvent(event)
            code=api.NotifyServiceStatusChangeW(int(handle),notification_mask(status['CurrentState']),ctypes.byref(notification))
            if code:raise manifest.PackageError('reader-status-notification-failed')
            while win32event.WaitForSingleObjectEx(event,win32event.INFINITE,True)==0xc0:pass
            if notification.error:raise manifest.PackageError('reader-status-notification-failed')
    finally:win32api.CloseHandle(event)


def reader_stop(remove=False):
    import pywintypes,win32api,win32con,win32event,win32service
    manager=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CONNECT)
    try:
        try:service=win32service.OpenService(manager,SERVICE,win32service.SERVICE_ALL_ACCESS)
        except pywintypes.error as error:
            if error.winerror==1060:return False
            raise
        try:
            if win32service.QueryServiceConfig(service)[3]!='"'+str(app_directory()/'TailD.exe')+'" reader-service':
                raise manifest.PackageError('unexpected-reader-service-identity')
            status=win32service.QueryServiceStatusEx(service);was_running=status['CurrentState']!=win32service.SERVICE_STOPPED
            process=None
            if status['ProcessId']:
                process=win32api.OpenProcess(win32con.SYNCHRONIZE,False,status['ProcessId'])
            try:
                if was_running:
                    if status['CurrentState']!=win32service.SERVICE_STOP_PENDING:
                        win32service.ControlService(service,win32service.SERVICE_CONTROL_STOP)
                    service_wait(service,win32service.SERVICE_STOPPED)
                if process is not None:win32event.WaitForSingleObject(process,win32event.INFINITE)
            finally:
                if process is not None:process.Close()
            if remove:win32service.DeleteService(service)
            return was_running
        finally:service.Close()
    finally:manager.Close()


def write_metadata(config,metadata):
    # This fixed protected work file is reserved installation metadata, not
    # arbitrary user content. A prior interrupted write can be replaced without
    # truncating the last committed owner/anti-replay state.
    pending=config.with_name('installation.pending.json');manifest.ordinary(pending)
    with pending.open('w',encoding='utf-8') as f:json.dump(metadata,f);f.flush();os.fsync(f.fileno())
    os.replace(pending,config)


def reader_start(directory,owner):
    import pywintypes,win32security,win32service
    sid=win32security.ConvertSidToStringSid(win32security.ConvertStringSidToSid(owner) if owner.startswith('S-') else win32security.LookupAccountName(None,owner)[0])
    config=directory/'installation.json'
    if config.exists():
        previous=json.loads(config.read_text(encoding='utf-8'))
        if previous['owner_sid']!=sid:raise manifest.PackageError('different-owner-requires-explicit-migration')
    else:
        with config.open('x',encoding='utf-8') as f:json.dump({'owner_sid':sid,'schema':'taild-installation-v1'},f)
    metadata=json.loads(config.read_text())
    metadata['highest_subversion']=max(metadata.get('highest_subversion',0),manifest.verify(directory,installed=True)['subversion'])
    write_metadata(config,metadata)
    manager=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CREATE_SERVICE|win32service.SC_MANAGER_CONNECT)
    try:
        command='"'+str(directory/'TailD.exe')+'" reader-service'
        try:
            service=win32service.CreateService(manager,SERVICE,'TailD read-only GlassWire reader',
                win32service.SERVICE_ALL_ACCESS,win32service.SERVICE_WIN32_OWN_PROCESS,
                win32service.SERVICE_AUTO_START,win32service.SERVICE_ERROR_NORMAL,command,None,0,None,None,None)
        except pywintypes.error as error:
            if error.winerror!=1073:raise
            service=win32service.OpenService(manager,SERVICE,win32service.SERVICE_ALL_ACCESS)
            if win32service.QueryServiceConfig(service)[3]!=command:
                service.Close();raise manifest.PackageError('unexpected-reader-service-identity')
        try:
            if win32service.QueryServiceStatusEx(service)['CurrentState']==win32service.SERVICE_STOPPED:
                win32service.StartService(service,None)
            service_wait(service,win32service.SERVICE_RUNNING)
        finally:service.Close()
    finally:manager.Close()


def copy_verified(source,destination,data):
    if destination.exists():raise manifest.PackageError('rollback-already-present')
    destination.mkdir()
    for name in [r['path'] for r in data['files']]+[manifest.MANIFEST,manifest.SIGNATURE,'installation.json']:
        path=source/name
        if not path.exists():continue
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    manifest.verify(destination,installed=True)


def remove_verified(root,data):
    # Exact signed members only, never a recursive sweep or an external source.
    manifest.verify(root,installed=True)
    for name in [r['path'] for r in data['files']]+[manifest.MANIFEST,manifest.SIGNATURE,'installation.json','installation.pending.json']:
        path=root/name
        if path.exists():manifest.ordinary(path);path.unlink()
    for directory in sorted((p for p in root.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
        if not any(directory.iterdir()):directory.rmdir()
    if not any(root.iterdir()):root.rmdir()


def prepare(candidate,owner=None):
    new=manifest.verify(candidate);app=app_directory();rollback=app.with_name('TailD.rollback')
    ensure_quiescent(app)
    if app.exists():
        old=manifest.verify(app,installed=True);manifest.newer(new,old)
        if owner is not None and json.loads((app/'installation.json').read_text())['owner_sid']!=owner:
            raise manifest.PackageError('different-owner-requires-explicit-migration')
        if new['subversion']<=json.loads((app/'installation.json').read_text()).get('highest_subversion',old['subversion']):
            raise manifest.PackageError('replay-after-rollback')
        if rollback.exists():
            previous=manifest.verify(rollback,installed=True);remove_verified(rollback,previous)
        running=reader_stop()
        try:copy_verified(app,rollback,old)
        except BaseException:
            if running:reader_start(app,json.loads((app/'installation.json').read_text())['owner_sid'])
            raise
        new_names={r['path'] for r in new['files']}
        for row in old['files']:
            if row['path'] not in new_names:(app/row['path']).unlink()
    return new


def blocks_installation(path,app,allow_uninstaller=False):
    return path.is_relative_to(app) and not (allow_uninstaller and path==app/'unins000.exe')


def ensure_quiescent(app,allow_uninstaller=False):
    import pywintypes,win32api,win32process,win32service
    manager=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CONNECT)
    service_pid=0
    try:
        try:service=win32service.OpenService(manager,SERVICE,win32service.SERVICE_QUERY_STATUS)
        except pywintypes.error as error:
            if error.winerror!=1060:raise
        else:
            try:service_pid=win32service.QueryServiceStatusEx(service)['ProcessId']
            finally:service.Close()
    finally:manager.Close()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype=wintypes.BOOL
    for pid in win32process.EnumProcesses():
        if pid in (0,os.getpid(),service_pid):continue
        try:process=win32api.OpenProcess(0x1000,False,pid)
        except pywintypes.error:continue
        try:
            buffer=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(buffer))
            if not kernel.QueryFullProcessImageNameW(int(process),0,buffer,ctypes.byref(size)):continue
            path=Path(buffer.value)
            if blocks_installation(path,app,allow_uninstaller):raise manifest.PackageError('close-taild-and-stop-collection-before-installing')
        finally:process.Close()


def update_registration(data):
    import winreg
    try:key=winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,UNINSTALL_KEY,0,winreg.KEY_SET_VALUE|winreg.KEY_WOW64_64KEY)
    except FileNotFoundError:return
    with key:
        winreg.SetValueEx(key,'DisplayVersion',0,winreg.REG_SZ,data['version'])
        winreg.SetValueEx(key,'DisplayName',0,winreg.REG_SZ,'TailD version '+data['version'])


def rollback(candidate=None,data=None):
    app=app_directory();previous=app.with_name('TailD.rollback')
    if Path(sys.executable).resolve().is_relative_to(app):
        raise manifest.PackageError('rollback-requires-detached-installer-helper')
    ensure_quiescent(app)
    old=manifest.verify(previous,installed=True)
    current=data if data is not None else manifest.verify(candidate) if candidate else manifest.verify(app,installed=True)
    metadata=json.loads(((app/'installation.json') if (app/'installation.json').exists() else previous/'installation.json').read_text())
    highest=max(metadata.get('highest_subversion',0),current['subversion'])
    reader_stop()
    old_names={r['path'] for r in old['files']}
    for row in current['files']:
        path=app/row['path']
        if row['path'] not in old_names and path.exists():
            with path.open('rb') as f:
                if manifest.hashlib.file_digest(f,'sha256').hexdigest()!=row['sha256']:
                    raise manifest.PackageError('changed-new-member-preserved')
            path.unlink()
    # Restore exact signed files; incompatible history migrations are refused by
    # the manifest schema. No SQLite history, credentials or node state is copied.
    for row in old['files']:
        source=previous/row['path'];target=app/row['path'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    for name in (manifest.MANIFEST,manifest.SIGNATURE):
        if (previous/name).exists():shutil.copyfile(previous/name,app/name)
    restored=json.loads((previous/'installation.json').read_text());restored['highest_subversion']=highest
    write_metadata(app/'installation.json',restored)
    manifest.verify(app,installed=True)
    update_registration(old)
    reader_start(app,json.loads((app/'installation.json').read_text())['owner_sid'])


def abort(candidate,data=None):
    app=app_directory()
    if app.with_name('TailD.rollback').exists():return rollback(candidate,data)
    data=data if data is not None else manifest.verify(candidate);ensure_quiescent(app);reader_stop(remove=True)
    # Fresh failed extraction: only remove candidate members whose current
    # bytes still match the signed input. Unknown or changed files survive.
    for row in data['files']:
        path=app/row['path']
        if not path.exists():continue
        manifest.ordinary(path)
        with path.open('rb') as f:digest=manifest.hashlib.file_digest(f,'sha256').hexdigest()
        if digest!=row['sha256']:raise manifest.PackageError('changed-partial-member-preserved')
    for row in data['files']:
        path=app/row['path']
        if path.exists():path.unlink()
    for name in (manifest.MANIFEST,manifest.SIGNATURE,'installation.json','installation.pending.json'):
        path=app/name
        if path.exists():manifest.ordinary(path);path.unlink()
    for directory in sorted((p for p in app.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
        manifest.ordinary(directory)
        if not any(directory.iterdir()):directory.rmdir()
    if app.exists() and not any(app.iterdir()):app.rmdir()


def check_uninstall():
    app=app_directory();ensure_quiescent(app,allow_uninstaller=True);manifest.verify(app,installed=True)
    previous=app.with_name('TailD.rollback')
    if previous.exists():manifest.verify(previous,installed=True)


def remove_history(dry_run=False):
    import history,reader
    config=json.loads((app_directory()/'installation.json').read_text())
    if config['owner_sid']!=reader.current_sid():raise manifest.PackageError('history-removal-requires-owning-account')
    root=known_folder(0x1c)/'TailD'/'history'
    if not root.exists():return
    history.private_directory(root)
    names={'history.sqlite3','history.sqlite3-journal','history.sqlite3-wal','history.sqlite3-shm',
        'desktop-queries.json','desktop-queries.pending.json',
        'runtime.json','runtime.pending.json','runtime-status.json','runtime-status.pending.json',
        'runtime-dns-progress.json','runtime-dns-progress.pending.json',
        'runtime-provider-limit.json','runtime-provider-limit.pending.json'}
    pending=[root];files=[];directories=[]
    while pending:
        directory=pending.pop();manifest.ordinary(directory);directories.append(directory)
        for path in directory.iterdir():
            manifest.ordinary(path)
            if path.is_dir():
                if directory==root and path.name!='ui-cache':raise manifest.PackageError('unrecognized-history-member')
                pending.append(path)
            elif directory!=root or path.name in names:files.append(path)
            else:raise manifest.PackageError('unrecognized-history-member')
    if dry_run:return
    for path in files:path.unlink()
    for directory in sorted(directories,key=lambda p:len(p.parts),reverse=True):directory.rmdir()


def uninstall(delete_history=False):
    check_uninstall()
    if delete_history:remove_history(dry_run=True)
    if manifest.verify(app_directory(),installed=True)['schema']=='taild-package-v2':
        import delivery
        # Return to the original migration baseline before Inno removes the
        # helper. Failure leaves the reader, credentials and history untouched.
        delivery.core_command(app_directory(),'unmigrate')
    if delete_history:remove_history()
    reader_stop(remove=True)
    previous=app_directory().with_name('TailD.rollback')
    if previous.exists():remove_verified(previous,manifest.verify(previous,installed=True))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('owner','owner-installed','verify','prepare','finish','stop','remove-reader','rollback','abort','remove-history','check-uninstall','uninstall','update','wait-parent','recover'))
    parser.add_argument('--candidate',type=Path);parser.add_argument('--owner');parser.add_argument('--owner-file',type=Path)
    parser.add_argument('--delete-history',action='store_true')
    parser.add_argument('--parent-pid',type=int);parser.add_argument('--parent-start',type=int)
    args=parser.parse_args(argv)
    if args.operation=='owner':
        import reader
        with args.owner_file.open('x',encoding='utf-8') as f:json.dump({'owner_sid':reader.current_sid(),'local_data':str(known_folder(0x1c))},f)
        return
    if args.operation=='verify':manifest.verify(args.candidate);return
    import win32security
    if not ctypes.windll.shell32.IsUserAnAdmin():raise manifest.PackageError('administrator-required')
    if args.operation=='owner-installed':
        import updater
        data=updater.owner()
        with args.owner_file.open('x',encoding='utf-8') as f:json.dump({'owner_sid':data['owner_sid'],'local_data':data['local_data']},f)
        return
    if args.operation=='wait-parent':
        import updater
        updater.wait_parent(args.parent_pid,args.parent_start);return
    if args.operation=='update':
        import updater
        updater.dispatch();return
    local_data=None
    if args.owner_file:
        original=json.loads(args.owner_file.read_bytes());args.owner=original['owner_sid'];local_data=original['local_data']
        win32security.ConvertStringSidToSid(args.owner)
        if not isinstance(local_data,str) or not Path(local_data).is_absolute():raise manifest.PackageError('invalid-owner-location')
    integrated=args.candidate is not None and manifest.verify(args.candidate)['schema']=='taild-package-v2'
    if args.operation=='rollback' and args.candidate is None and manifest.verify(app_directory(),installed=True)['schema']=='taild-package-v2':
        raise manifest.PackageError('complete-detached-recovery-package-required')
    if args.operation=='prepare':
        if integrated:
            import delivery,updater
            if app_directory().exists():
                journal=delivery.read_journal()
                if journal is not None and journal['phase'] not in ('complete','recovered'):
                    delivery.journal_manifest(journal,'new')
                    updater.graceful_stop({'owner_sid':journal['owner_sid'],'local_data':journal['local_data']})
                else:updater.graceful_stop(updater.owner())
            delivery.prepare(args.candidate,args.owner,local_data)
        else:prepare(args.candidate,args.owner)
    elif args.operation=='finish':
        if integrated:
            import delivery
            delivery.finish(args.candidate);return
        app=app_directory();manifest.verify(app,installed=True)
        sid=win32security.ConvertSidToStringSid(win32security.ConvertStringSidToSid(args.owner))
        reader_start(app,sid)
    elif args.operation=='stop':reader_stop()
    elif args.operation=='remove-reader':reader_stop(remove=True)
    elif args.operation=='remove-history':remove_history()
    elif args.operation=='check-uninstall':check_uninstall()
    elif args.operation in ('abort','recover'):
        if integrated:
            import delivery,updater
            journal=delivery.read_journal()
            if journal is not None and journal['phase'] not in ('complete','recovered'):
                delivery.journal_manifest(journal,'new')
                updater.graceful_stop({'owner_sid':journal['owner_sid'],'local_data':journal['local_data']})
            delivery.recover(args.candidate)
        else:abort(args.candidate)
    elif args.operation=='uninstall':
        uninstall(args.delete_history)
    else:
        if integrated:
            import delivery,updater
            updater.graceful_stop(updater.owner());delivery.rollback(args.candidate)
        else:rollback(args.candidate)


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit(1)
