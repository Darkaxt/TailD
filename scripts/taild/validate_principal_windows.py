"""Authorized isolated different-account probe through the shared elevation gate."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import threading
import uuid

import credentials
import history
import reader


def run(directory, probe, title):
    directory.mkdir(parents=True,exist_ok=False)
    store=history.History(directory/'history');store.close()
    name='principal-'+uuid.uuid4().hex
    control=reader.PipeServer(name,reader.current_sid(),reader.GlassWireSource())
    thread=threading.Thread(target=control.serve,name='TailD different-principal probe pipe')
    thread.start();control.ready.wait()
    vault=credentials.CredentialStore('TailD/test/'+uuid.uuid4().hex)
    secret='synthetic-only-'+uuid.uuid4().hex
    vault.replace(secret)
    script=Path(__file__).with_name('validate_principal_admin.ps1').resolve()
    output=directory/'principal-validation.json'
    try:
        command=[sys.executable,'-B',r'C:\Users\darka\.agents\skills\windows-elevation-gate\scripts\invoke_windows_elevation_gate.py',
            'run','--owner-task','TailD Stage 7 different-account isolation validation',
            '--thread-name',title,'--reason','Verify that a real non-admin Windows identity cannot read TailD history, IPC or the user vault.',
            '--changes','Create and remove one temporary LocalService verification task; grant access only to generated probe binaries and its status file. No VPN, DNS, firewall, source ACL or installed client changes.',
            '--target',str(directory),'--cwd',str(script.parent),
            '--bind-file',str(script),'--bind-file',str(probe),'--bind-file',str(probe.with_suffix('.dll')),
            '--',r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden',
            '-File',str(script),'-Probe',str(probe),'-History',str(directory/'history'/'history.sqlite3'),
            '-Pipe',reader.pipe_name(name),'-Credential',vault.target,'-Output',str(output)]
        result=subprocess.run(command,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        print(result.stdout)
        if result.returncode:
            raise reader.ReaderError('elevated-probe-not-complete')
        gate=json.loads(result.stdout)
        if not gate.get('ok') or not output.exists():
            raise reader.ReaderError('elevated-probe-not-verified')
        report=json.loads(output.read_text())
        assert report['sid']=='S-1-5-19' and not report['administrator']
        assert report['history_denied'] and report['pipe_denied'] and not report['credential_read']
        assert vault.read()==secret,'Owning user synthetic credential was changed'
        print(json.dumps({'actual_different_nonadmin_principal':True,'history_denied':True,
            'pipe_denied':True,'vault_isolated':True,'production_credential_changed':False}))
    finally:
        vault.remove()
        assert vault.read() is None
        control.stop();thread.join()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--thread-name',required=True)
    args=parser.parse_args()
    run(args.output,args.probe.resolve(strict=True),args.thread_name)
