"""Explicit temporary protected-source validation; no service/task installation.

The supervisor remains unelevated. Only the fixed read-only reader prompts for
UAC. Its readiness, shutdown and process exit are observed through native events.
No token is recovered, persisted or passed to the elevated reader.
"""
import argparse
from datetime import datetime, timedelta, timezone
import http.client
import json
from pathlib import Path
import subprocess
import sys
import uuid

import history
import reader
import runtime


def run(directory, cli=None, reuse_owned_history=False):
    import pywintypes
    import win32api
    import win32con
    import win32event
    import win32pipe
    import win32process
    import win32security
    from win32com.shell import shell, shellcon

    directory = history.private_directory(directory)
    # One-day retention is an explicit isolated validation choice, not a changed
    # product default or an installed collector's configuration.
    store = history.History(directory, retention_days=1)
    store.close()
    instance = 'live-' + uuid.uuid4().hex
    event_name = 'Local\\Darkaxt.TailD.Ready.' + instance
    owner = reader.current_sid()
    sa = pywintypes.SECURITY_ATTRIBUTES()
    sa.SECURITY_DESCRIPTOR = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
        'D:P(A;;GA;;;SY)(A;;GA;;;'+owner+')',win32security.SDDL_REVISION_1)
    ready = win32event.CreateEvent(sa,True,False,event_name)
    process = None
    client = None
    collector = None
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    if not pythonw.is_file():
        raise runtime.RuntimeError('no-console-runtime-required')
    try:
        parameters = subprocess.list2cmdline(['-B',str(Path(reader.__file__).resolve()),
            '--instance',instance,'--owner-sid',owner,'--ready-event',event_name])
        launched = shell.ShellExecuteEx(fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
            lpVerb='runas',lpFile=str(pythonw),lpParameters=parameters,
            lpDirectory=str(Path(reader.__file__).resolve().parent),nShow=win32con.SW_HIDE)
        process = launched['hProcess']
        outcome = win32event.WaitForMultipleObjects([ready,process],False,win32event.INFINITE)
        if outcome != win32event.WAIT_OBJECT_0:
            raise runtime.RuntimeError('reader-exited-before-ready')
        pid = win32process.GetProcessId(process)
        token = win32security.OpenProcessToken(process,win32con.TOKEN_QUERY)
        try:
            elevated = bool(win32security.GetTokenInformation(token,win32security.TokenElevation))
            privileges = [win32security.LookupPrivilegeName(None,luid) for luid,_ in
                          win32security.GetTokenInformation(token,win32security.TokenPrivileges)]
        finally:
            token.Close()
        if not elevated or set(privileges)-{'SeChangeNotifyPrivilege','SeImpersonatePrivilege'}:
            raise runtime.RuntimeError('unexpected-reader-privileges')
        client = reader.PipeClient(instance)
        catalog = client.discover()
        collector = runtime.Collector(directory,client,instance=instance,cli=cli)
        collector.start()
        if collector.command('state')['state'] != 'disabled' and not reuse_owned_history:
            raise runtime.RuntimeError('validation-history-already-enabled')
        collector.command('configure',{'traffic':True,'dns':False,'host_scope':'explicit-live-windows-validation'})
        state = collector.command('refresh')
        if state['sources']['traffic']['state'] != 'collecting' or 'last_success_utc' not in state['sources']['traffic']:
            raise runtime.RuntimeError('protected-source-acquisition-failed')
        collector.command('pause')
        end = datetime.now(timezone.utc).replace(microsecond=0)
        start = end-timedelta(minutes=15)
        query = {'kind':'traffic','view':'summary','start':start.isoformat(),'end':end.isoformat(),
                 'scope':{'host':'explicit-live-windows-validation'}}
        session = collector.session()
        connection = http.client.HTTPConnection('127.0.0.1',session['port'])
        try:
            connection.request('POST','/api/query',json.dumps({'queries':[query]}),
                headers={'Authorization':'Bearer '+session['token'],'Origin':session['origin'],'Content-Type':'application/json'})
            response = connection.getresponse()
            data = json.loads(response.read())
            if response.status != 200:
                raise runtime.RuntimeError('authenticated-live-query-failed')
        finally:
            connection.close()
        if collector.command('state')['state'] != 'paused':
            raise runtime.RuntimeError('window-close-altered-collection')
        before = data['results'][0]['data']
        collector.close()
        collector = runtime.Collector(directory,client,instance=instance,cli=cli)
        collector.start()
        collector.command('pause')
        reopened = collector.command('query',{'queries':[query]})['results'][0]['data']
        # Startup can reconcile mutable source rows. Compare values only after
        # pause; differences are observed corrections, not presumed duplicates.
        report = {'source_version':catalog['version'],'reader_pid':pid,
            'reader_elevated':elevated,'reader_privileges':privileges,
            'collector_elevated':False,'authenticated_query':True,'pause_restart_query':True,
            'observed_traffic_buckets':reopened['application_activity']['bucket_count'],
            'observed_total_bytes':str(reopened['data']['total_bytes']),
            'unchanged_during_restart':before['data']==reopened['data'],
            'completeness':'query coverage retained; no universal source finalization claim',
            'provider_runtime':'not-tested-no-credential-installed',
            'network_configuration_changed':False,'service_or_task_installed':False}
        collector.close()
        collector = None
        client.close()
        client = None
        # This is an actual native availability transition, not a retry delay.
        win32pipe.WaitNamedPipe(reader.pipe_name(instance),win32pipe.NMPWAIT_WAIT_FOREVER)
        control = reader.PipeClient(instance)
        try:
            control.request({'op':'shutdown'})
        finally:
            control.close()
        win32event.WaitForSingleObject(process,win32event.INFINITE)
        if win32process.GetExitCodeProcess(process) != 0:
            raise runtime.RuntimeError('reader-exit-failed')
        report['reader_exit_verified'] = True
        target = directory/'runtime-validation.json'
        with target.open('x',encoding='utf-8') as output:
            json.dump(report,output,indent=2)
        return report
    finally:
        if collector is not None:
            collector.close()
        if client is not None:
            client.close()
        if process is not None:
            if win32event.WaitForSingleObject(process,0) != win32event.WAIT_OBJECT_0:
                win32pipe.WaitNamedPipe(reader.pipe_name(instance),win32pipe.NMPWAIT_WAIT_FOREVER)
                control = reader.PipeClient(instance)
                try:
                    control.request({'op':'shutdown'})
                finally:
                    control.close()
                win32event.WaitForSingleObject(process,win32event.INFINITE)
            win32api.CloseHandle(process)
        win32api.CloseHandle(ready)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-only-live',required=True,action='store_true')
    parser.add_argument('--history',required=True)
    parser.add_argument('--cli')
    parser.add_argument('--reuse-owned-history',action='store_true',
                        help='Explicitly reuse this task-owned isolated validation history')
    args = parser.parse_args(argv)
    try:
        report = run(args.history,args.cli,args.reuse_owned_history)
        print(json.dumps(report))
        return 0
    except Exception as error:
        # No path, provider value, token, native traceback or source records.
        import traceback
        frames = [{'file':Path(f.filename).name,'line':f.lineno,'function':f.name}
                  for f in traceback.extract_tb(error.__traceback__)]
        print(json.dumps({'state':'validation-not-complete','error_type':type(error).__name__,'frames':frames}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
