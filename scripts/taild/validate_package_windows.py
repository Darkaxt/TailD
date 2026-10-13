"""Destructive installer acceptance ONLY on a fresh GitHub-hosted Windows VM.

Fixture trust and opaque synthetic account state are not a production signature
or an authenticated tailnet test. No real credentials or network service used.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import installer
import package_manifest as manifest
import signing


def hosted_only():
    if os.name!='nt' or os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise RuntimeError('Installer acceptance requires a fresh GitHub-hosted Windows runner')
    if not installer.ctypes.windll.shell32.IsUserAnAdmin():raise RuntimeError('Hosted runner administrator token required')


def run(command,expected=0):
    result=subprocess.run([str(value) for value in command],check=False)
    if expected==0 and result.returncode!=0 or expected!=0 and result.returncode==0:
        raise AssertionError('Unexpected process exit: '+Path(command[0]).name+' '+str(result.returncode))
    return result.returncode


def provision():
    import pywintypes,win32cred
    hosted_only()
    try:win32cred.CredRead(signing.TARGET,win32cred.CRED_TYPE_GENERIC)
    except pywintypes.error as error:
        if error.winerror!=1168:raise
    else:raise RuntimeError('Refuse an existing signing identity')
    key=signing.private_key(create=True)
    public=base64.b64encode(key.public_key().public_bytes_raw()).decode()
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as output:output.write('public_key='+public+'\n')


def sign_package(candidate,key):
    package=candidate/'payload'/'TailD'
    provenance=json.loads((candidate/'provenance.json').read_text(encoding='utf-8'))
    if provenance['source_dirty'] or not provenance['fixture_trust']:raise AssertionError('Clean fixture build required')
    data=manifest.validate({'schema':'taild-package-v1','product':'TailD','upstream_version':provenance['upstream_version'],
        'subversion':provenance['subversion'],'version':provenance['upstream_version']+'+'+str(provenance['subversion']),
        'architecture':'windows-amd64','source_commit':provenance['source_commit'],'core_replace':provenance['core_replace'],
        'history_schema':4,'authenticode':'not-signed','files':manifest.inventory(package)})
    raw=json.dumps(data,sort_keys=True,separators=(',',':')).encode()
    with (package/manifest.MANIFEST).open('xb') as output:output.write(raw)
    with (package/manifest.SIGNATURE).open('xb') as output:output.write(key.sign(raw))
    return package,data


def service_snapshot():
    import win32service
    manager=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CONNECT)
    try:service=win32service.OpenService(manager,'Tailscale',win32service.SERVICE_QUERY_CONFIG|win32service.SERVICE_QUERY_STATUS)
    finally:manager.Close()
    try:return {'config':list(win32service.QueryServiceConfig(service)),'status':win32service.QueryServiceStatusEx(service)}
    finally:service.Close()


def acceptance(root,compiler,repo):
    import pywintypes,win32api,win32cred,win32security,win32service
    import history,reader,packaged
    hosted_only()
    app=installer.app_directory()
    if app.parent.exists():raise RuntimeError('Refuse pre-existing connectivity installation')
    manager=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CREATE_SERVICE|win32service.SC_MANAGER_CONNECT)
    for name in ('Tailscale',installer.SERVICE):
        try:service=win32service.OpenService(manager,name,win32service.SERVICE_QUERY_STATUS)
        except pywintypes.error as error:
            if error.winerror!=1060:raise
        else:service.Close();manager.Close();raise RuntimeError('Refuse existing service')
    # A stopped, explicitly synthetic SCM entry verifies preservation, without
    # starting another VPN or pretending these bytes are real node secrets.
    service=win32service.CreateService(manager,'Tailscale','Synthetic Tailscale preservation fixture',
        win32service.SERVICE_ALL_ACCESS,win32service.SERVICE_WIN32_OWN_PROCESS,
        win32service.SERVICE_DEMAND_START,win32service.SERVICE_ERROR_NORMAL,
        '"'+str(Path(os.environ['WINDIR'])/'System32'/'cmd.exe')+'" /c exit 0',None,None,None,None,None)
    service.Close();manager.Close()
    app.parent.mkdir(parents=True)
    sentinel=app.parent/'synthetic-node-tailnet-lock-provider.state'
    sentinel.write_bytes(b'SYNTHETIC OPAQUE ACCOUNT/NODE/SIGNER/DNS FIXTURE; NOT A REAL CREDENTIAL')
    before=service_snapshot();before_hash=hashlib.sha256(sentinel.read_bytes()).hexdigest()
    key=signing.private_key();public=base64.b64encode(key.public_key().public_bytes_raw()).decode()
    report={'schema':'taild-package-acceptance-v1','production_trust':False,'authenticode':False,
        'account_state':'synthetic opaque preservation fixture, not authenticated tailnet','checks':[],'packages':[]}
    report_path=root/'installer-acceptance.json'
    def check(name):
        assert service_snapshot()==before and hashlib.sha256(sentinel.read_bytes()).hexdigest()==before_hash
        report['checks'].append(name)
        report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('Verified: '+name,flush=True)
    def helper(operation,*arguments,expected=0):
        diagnostic=root/('helper-'+str(len(list(root.glob('helper-*.json'))))+'.json')
        command=[app/'TailD.Setup.exe',operation,*arguments,'--result',diagnostic]
        code=run(command,expected)
        if diagnostic.exists():print(diagnostic.read_text(encoding='utf-8'),flush=True)
        return code
    setups=[]
    try:
        for index in (1,2):
            package,data=sign_package(root/('candidate-'+str(index)),key)
            manifest.verify(package,public)
            out=root/('installer-'+str(index))
            run([compiler,'/Q','/DPayload='+str(package),'/DProductVersion='+data['version'],
                 '/DOutputPath='+str(out),repo/'desktop'/'installer.iss'])
            setup=out/('TailD-'+data['version']+'-windows-amd64-setup.exe');setups.append(setup)
            report['packages'].append({'version':data['version'],'source_commit':data['source_commit'],
                'core_replace':data['core_replace'],'installer_sha256':hashlib.sha256(setup.read_bytes()).hexdigest()})
        run([setups[0],'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(root/'install-1.log')])
        assert manifest.verify(app,public,True)['subversion']==1
        sid=reader.current_sid()
        assert json.loads((app/'installation.json').read_text())['owner_sid']==sid
        # Real LocalSystem service -> SID-authenticated actual pipe -> explicit
        # unavailable GlassWire source on the clean runner, never fake records.
        client=reader.PipeClient(packaged.reader_instance(sid))
        try:
            with_source=False
            try:client.request({'op':'catalog'});with_source=True
            except reader.ReaderError as error:assert error.state=='source-unavailable',error.state
            assert not with_source,'Clean runner unexpectedly contains GlassWire source'
        finally:client.close()
        check('fresh-install-reader-SCM-owner-pipe-source-unavailable')
        local=installer.known_folder(0x1c)/'TailD';history.private_directory(local)
        home=history.private_directory(local/'history')
        store=history.History(home);store.close()
        history_hash=hashlib.sha256((home/'history.sqlite3').read_bytes()).hexdigest()
        helper('check-uninstall')
        manager=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CONNECT)
        try:service=win32service.OpenService(manager,installer.SERVICE,win32service.SERVICE_QUERY_STATUS)
        finally:manager.Close()
        try:assert win32service.QueryServiceStatusEx(service)['CurrentState']==win32service.SERVICE_RUNNING
        finally:service.Close()
        check('uninstall-preflight-preserves-running-reader-and-history')
        run([setups[1],'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(root/'upgrade-2.log')])
        assert manifest.verify(app,public,True)['subversion']==2
        assert hashlib.sha256((home/'history.sqlite3').read_bytes()).hexdigest()==history_hash
        check('upgrade-preserves-history-source-and-account-state')
        helper('prepare','--candidate',root/'candidate-1'/'payload'/'TailD',expected=1)
        assert manifest.verify(app,public,True)['subversion']==2
        check('replay-rejected-without-installed-mutation')
        helper('rollback')
        assert manifest.verify(app,public,True)['subversion']==1
        assert json.loads((app/'installation.json').read_text())['highest_subversion']==2
        helper('prepare','--candidate',root/'candidate-2'/'payload'/'TailD',expected=1)
        check('rollback-restores-payload-service-and-retains-anti-replay-watermark')
        # Tamper one trusted candidate member, ensure rejection, then restore
        # that exact test-owned byte sequence before further use.
        candidate=root/'candidate-2'/'payload'/'TailD';target=candidate/'desktop'/'ui'/'index.html'
        original=target.read_bytes();target.write_bytes(original+b'\nTAMPER FIXTURE')
        try:helper('prepare','--candidate',candidate,expected=1)
        finally:target.write_bytes(original)
        check('tampered-payload-rejected')
        run([app/'unins000.exe','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(root/'uninstall-retain.log')])
        assert (home/'history.sqlite3').exists() and not (app/'TailD.exe').exists()
        check('normal-uninstall-retains-history-and-connectivity-state')
        run([setups[1],'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(root/'reinstall-2.log')])
        helper('remove-history')
        assert not home.exists()
        run([app/'unins000.exe','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(root/'uninstall-remove.log')])
        check('explicit-own-history-removal-and-uninstall')
        report['ok']=True
    finally:
        report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        # Only ephemeral fixture credential and exact synthetic stopped service.
        win32cred.CredDelete(signing.TARGET,win32cred.CRED_TYPE_GENERIC)
        manager=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CONNECT)
        try:
            service=win32service.OpenService(manager,'Tailscale',win32service.DELETE)
            try:win32service.DeleteService(service)
            finally:service.Close()
        finally:manager.Close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('provision','acceptance'))
    parser.add_argument('--root',type=Path);parser.add_argument('--compiler',type=Path)
    args=parser.parse_args()
    if args.operation=='provision':provision()
    else:acceptance(args.root,args.compiler,Path(__file__).resolve().parents[2])
