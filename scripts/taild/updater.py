"""Fixed administrator updater dispatch for the dedicated TailD installer channel."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import uuid

import delivery
import history
import installer
import maintenance
import package_manifest as manifest
import release_channel


def owner():
    app=installer.app_directory();manifest.verify(app,installed=True)
    data=json.loads((app/'installation.json').read_bytes())
    if not isinstance(data.get('local_data'),str) or not Path(data['local_data']).is_absolute():
        raise manifest.PackageError('installed-owner-location-unavailable')
    import win32security
    win32security.ConvertStringSidToSid(data['owner_sid'])
    return data


def process_image(handle):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype=wintypes.BOOL
    buffer=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(buffer))
    if not kernel.QueryFullProcessImageNameW(int(handle),0,buffer,ctypes.byref(size)):return None
    return Path(buffer.value)


def process_creation(handle):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4)]
    kernel.GetProcessTimes.restype=wintypes.BOOL
    values=[wintypes.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(int(handle),*[ctypes.byref(value) for value in values]):
        raise manifest.PackageError('update-parent-identity-unavailable')
    return (values[0].dwHighDateTime<<32)|values[0].dwLowDateTime


def wait_parent(pid,created):
    import pywintypes,win32api,win32con,win32event
    try:handle=win32api.OpenProcess(win32con.SYNCHRONIZE|0x1000,False,pid)
    except pywintypes.error as error:
        if error.winerror==87:return
        raise
    try:
        if process_creation(handle)!=created:return  # Original identity exited; PID was reused.
        if process_image(handle)!=installer.app_directory()/'TailD.Setup.exe':
            raise manifest.PackageError('unexpected-update-parent')
        win32event.WaitForSingleObject(handle,win32event.INFINITE)
    finally:handle.Close()


def graceful_stop(config):
    import pywintypes,win32api,win32con,win32event,win32gui,win32process,win32service
    app=installer.app_directory()
    home=Path(config['local_data'])/'TailD'/'history'
    instance='owner-'+history.digest([config['owner_sid'],str(home).casefold()])[:32]
    manager=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CONNECT)
    reader_pid=0
    try:
        try:service=win32service.OpenService(manager,installer.SERVICE,win32service.SERVICE_QUERY_STATUS)
        except pywintypes.error as error:
            if error.winerror!=1060:raise
        else:
            try:reader_pid=win32service.QueryServiceStatusEx(service)['ProcessId']
            finally:service.Close()
    finally:manager.Close()
    handles={}
    try:
        for pid in win32process.EnumProcesses():
            if pid in (0,os.getpid(),reader_pid):continue
            try:process=win32api.OpenProcess(win32con.SYNCHRONIZE|0x1000,False,pid)
            except pywintypes.error:continue
            image=process_image(process)
            if image is None or not image.is_relative_to(app):process.Close();continue
            handles[pid]=process
        if handles:
            signaled=maintenance.signal(config['owner_sid'],instance)
            def close_window(window,_):
                _,pid=win32process.GetWindowThreadProcessId(window)
                if pid in handles:win32gui.PostMessage(window,win32con.WM_CLOSE,0,0)
            win32gui.EnumWindows(close_window,None)
            # Never wait on an unidentified frozen worker indefinitely. Its
            # event must exist before it can be accepted as update-cooperative.
            if not signaled:raise manifest.PackageError('collector-update-readiness-unavailable')
            for handle in handles.values():win32event.WaitForSingleObject(handle,win32event.INFINITE)
    finally:
        for handle in handles.values():handle.Close()
    installer.ensure_quiescent(app)


def dispatch():
    import win32api,win32event
    # Global cross-session collision control, independent of the interactive
    # prompt queue and of the Inno installer transaction mutex.
    lock=win32event.CreateMutex(None,False,'Global\\Darkaxt.TailD.UpdateDownload')
    owned=False
    try:
        selected=win32event.WaitForSingleObject(lock,0)
        if selected==win32event.WAIT_TIMEOUT:return  # Diagnostic collision, no operation is canceled.
        if selected not in (win32event.WAIT_OBJECT_0,win32event.WAIT_ABANDONED):raise manifest.PackageError('update-lock-unavailable')
        owned=True
        config=owner();app=installer.app_directory();current=manifest.verify(app,installed=True)
        root=delivery.state_directory()/'updates'/uuid.uuid4().hex
        try:executable,data=release_channel.prepare(root,config['highest_subversion'],current['upstream_version'])
        except release_channel.ChannelError as error:
            if str(error)=='release-replay-or-downgrade':return
            raise
        graceful_stop(config)
        parent_created=process_creation(win32api.GetCurrentProcess())
        # Inno waits for this exact helper identity to exit before replacing any
        # loaded library. No self-overwrite, delay or race with DLL unmapping.
        command=[str(executable),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TAILDAUTO=1',
            '/TAILDPARENTPID='+str(os.getpid()),'/TAILDPARENTSTART='+str(parent_created),
            '/LOG='+str(root/'installer.log')]
        subprocess.Popen(command,creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_BREAKAWAY_FROM_JOB)
    finally:
        if owned:win32event.ReleaseMutex(lock)
        win32api.CloseHandle(lock)
