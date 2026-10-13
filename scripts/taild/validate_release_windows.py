"""Hook-free production native UI + frozen collector, no installed mutations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

import history
import reader


def run(package,output):
    import win32api,win32con,win32event,win32gui
    output.mkdir(parents=True,exist_ok=False)
    home=history.private_directory(output/'history')
    instance='release-'+uuid.uuid4().hex
    ready_name='Local\\Darkaxt.TailD.Ready.'+instance
    event=win32event.CreateEvent(None,True,False,ready_name)
    collector=subprocess.Popen([str(package/'TailD.exe'),'collector','run','--history',str(home),
        '--reader-instance','deliberately-unavailable-offline-source','--instance',instance,'--ready-event',ready_name],
        creationflags=subprocess.CREATE_NO_WINDOW)
    native=None
    try:
        selected=win32event.WaitForMultipleObjects([event,int(collector._handle)],False,win32event.INFINITE)
        if selected!=win32event.WAIT_OBJECT_0:raise AssertionError('Frozen collector exited before readiness')
        native=subprocess.Popen([str(package/'desktop'/'TailD.Desktop.exe'),'--instance',instance,
            '--collector-pid',str(collector.pid),'--user-data',str(home/'ui-cache')],creationflags=subprocess.CREATE_NO_WINDOW)
        powershell=Path(os.environ['WINDIR'])/'System32'/'WindowsPowerShell'/'v1.0'/'powershell.exe'
        probe=Path(__file__).with_name('validate_release_window.ps1')
        subprocess.run([str(powershell),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(probe),
            '-NativePid',str(native.pid),'-Output',str(output/'rendered.json')],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        rendered=json.loads((output/'rendered.json').read_text(encoding='utf-8-sig'))
        screenshot=Path(os.environ['USERPROFILE'])/'.codex'/'skills'/'screenshot'/'scripts'/'take_screenshot.ps1'
        subprocess.run([str(powershell),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(screenshot),
            '-WindowHandle',str(rendered['window_handle']),'-Path',str(output/'release-window.png')],check=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
        # The UI intentionally owns the single authenticated control pipe.
        # Read the existing redacted diagnostics, not a competing connection.
        state=json.loads((home/'runtime-status.json').read_text(encoding='utf-8'))
        assert state['owner_pid']==collector.pid and state['state']=='disabled'
        assert state['sources']['traffic']['state']=='disabled' and state['sources']['dns']['state']=='disabled'
        report={'ok':True,'debug_hooks':False,'frozen_collector':True,'offline_source':'deliberately unavailable',
            'collection_state':'disabled, no provider credential or source read',
            'fingerprints':{name:hashlib.sha256((package/name).read_bytes()).hexdigest()
                for name in ('TailD.exe','desktop/TailD.Desktop.dll','desktop/ui/index.html')}}
    finally:
        win32api.CloseHandle(event)
        if native is not None and native.poll() is None:
            windows=[]
            import win32process
            win32gui.EnumWindows(lambda window,_:windows.append(window) if win32process.GetWindowThreadProcessId(window)[1]==native.pid else None,None)
            for window in windows:win32gui.PostMessage(window,win32con.WM_CLOSE,0,0)
            native.wait()
        if collector.poll() is None:
            client=reader.PipeClient(instance)
            try:client.request({'op':'shutdown'})
            except reader.ReaderError:pass # Native window close may already have stopped its pipe.
            finally:client.close()
        collector.wait()
    assert collector.returncode==0 and native.returncode==0
    (output/'release-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();run(args.package,args.output)
