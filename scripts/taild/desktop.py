"""Explicit owning-user desktop launcher; no install, startup entry or elevation."""
import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys

import history
import reader


def server_pid(instance):
    import win32file, win32con, win32api
    handle = win32file.CreateFile(reader.pipe_name(instance),reader.CLIENT_ACCESS,0,None,
        win32con.OPEN_EXISTING,win32con.SECURITY_SQOS_PRESENT|0x10000,None)
    try:
        pid=ctypes.c_ulong()
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.GetNamedPipeServerProcessId.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        api.GetNamedPipeServerProcessId.restype=wintypes.BOOL
        if not api.GetNamedPipeServerProcessId(int(handle),ctypes.byref(pid)):
            raise reader.ReaderError('unavailable')
        return pid.value
    finally:
        win32api.CloseHandle(handle)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell',required=True)
    parser.add_argument('--history',required=True)
    parser.add_argument('--reader-instance',required=True)
    parser.add_argument('--cli')
    parser.add_argument('--debug-port',type=int)
    parser.add_argument('--validation-ready-event',help='Debug host readiness event; ignored by release host')
    args=parser.parse_args(argv)
    import pywintypes, win32api, win32event
    home=history.private_directory(args.history)
    instance='owner-'+history.digest([reader.current_sid(),str(home).casefold()])[:32]
    shell=Path(args.shell).resolve(strict=True)
    frozen=getattr(sys,'frozen',False)
    pythonw=Path(sys.executable).resolve(strict=True) if frozen else Path(sys.executable).with_name('pythonw.exe').resolve(strict=True)
    worker=None
    try:
        pid=server_pid(instance)
    except pywintypes.error as error:
        if error.winerror!=2:
            raise reader.ReaderError('unavailable') from None
        ready_name='Local\\Darkaxt.TailD.Ready.'+instance
        ready=win32event.CreateEvent(None,True,False,ready_name)
        try:
            command=[str(pythonw),*(['collector'] if frozen else ['-B',str(Path(__file__).with_name('runtime.py'))]),'run',
                '--history',str(home),'--reader-instance',args.reader_instance,'--instance',instance,'--ready-event',ready_name]
            if args.cli:command+=['--cli',args.cli]
            worker=subprocess.Popen(command,creationflags=subprocess.CREATE_NO_WINDOW)
            result=win32event.WaitForMultipleObjects([ready,int(worker._handle)],False,win32event.INFINITE)
            if result!=win32event.WAIT_OBJECT_0:
                worker.wait()
                raise reader.ReaderError('startup-failed')
            pid=worker.pid
        finally:
            win32api.CloseHandle(ready)
    command=[str(shell),'--instance',instance,'--collector-pid',str(pid),'--user-data',str(home/'ui-cache')]
    if args.debug_port:command+=['--debug-port',str(args.debug_port)]
    if args.validation_ready_event:
        if args.validation_ready_event!='Local\\Darkaxt.TailD.UIReady.'+instance:
            raise reader.ReaderError('invalid-ready-event')
        command+=['--validation-ready-event',args.validation_ready_event]
    try:
        return subprocess.run(command,creationflags=subprocess.CREATE_NO_WINDOW).returncode
    finally:
        # The native connection owns ordinary closure; launch failure must also
        # release a disabled runtime. Enabled collection remains intentional.
        client=reader.PipeClient(instance)
        try:
            detached=client.request({'op':'window-closed'})
            if not detached['collector_continues'] and worker is not None:
                worker.wait()
        except reader.ReaderError:
            if worker is not None and worker.poll() is not None:worker.wait()
        finally:
            client.close()


if __name__=='__main__':
    raise SystemExit(main())
