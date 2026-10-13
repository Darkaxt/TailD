"""One installer transaction across the inherited VPN binaries and analytics.

The external verified candidate owns recovery. Journal manifests are separately
verified against the embedded key; paths/commands never come from that journal.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess

import installer
import package_manifest as manifest

PHASES={'preparing','prepared','core_started','core_complete','complete','core_restored','recovered'}


def state_directory():
    import win32security
    root=installer.known_folder(0x23)/'TailD'
    for parent in (root,*root.parents):
        if parent.exists():manifest.ordinary(parent)
    root.mkdir(exist_ok=True)
    descriptor=win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
        'D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)',win32security.SDDL_REVISION_1)
    win32security.SetNamedSecurityInfo(str(root),win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION|win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,None,descriptor.GetSecurityDescriptorDacl(),None)
    return root


def write_journal(data):
    root=state_directory();pending=root/'setup-transaction.pending.json';manifest.ordinary(pending)
    with pending.open('w',encoding='utf-8') as output:
        json.dump(data,output,separators=(',',':'));output.flush();os.fsync(output.fileno())
    os.replace(pending,root/'setup-transaction.json')


def read_journal():
    path=state_directory()/'setup-transaction.json'
    if not path.exists():return None
    manifest.ordinary(path)
    if path.stat().st_size>6*1024*1024:raise manifest.PackageError('invalid-installation-journal')
    data=json.loads(path.read_bytes())
    if data.get('schema')!='taild-setup-transaction-v1' or data.get('phase') not in PHASES:
        raise manifest.PackageError('invalid-installation-journal')
    return data


def journal_manifest(journal,which):
    return manifest.verify_bytes(base64.b64decode(journal[which+'_manifest'],validate=True),
        base64.b64decode(journal[which+'_signature'],validate=True))


def record_manifest(journal,which,root):
    journal[which+'_manifest']=base64.b64encode((root/manifest.MANIFEST).read_bytes()).decode()
    journal[which+'_signature']=base64.b64encode((root/manifest.SIGNATURE).read_bytes()).decode()


def core_command(candidate,action):
    # The candidate and complete signed member inventory have been verified by
    # the caller. Inherited helper independently verifies its dedicated signed
    # core manifest on install/update. No token or DNS override is passed.
    payload=Path(candidate)/'connectivity'
    result=subprocess.run([str(payload/'taildns-installer.exe'),'-action',action,'-payload',str(payload)],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise manifest.PackageError('connectivity-'+action+'-failed')
    # Inherited output includes whitelisted node identity. Never put it in the
    # ordinary setup diagnostic log or a public workflow artifact.
    return json.loads(result.stdout)


def rollback_core(candidate,journal):
    data=journal_manifest(journal,'new')
    root=state_directory();started=False
    for name in ('deployment-v4.json','deployment-v4.json.rollback'):
        path=root/name
        if not path.exists():continue
        manifest.ordinary(path)
        if path.stat().st_size>1024*1024:raise manifest.PackageError('invalid-connectivity-record')
        if json.loads(path.read_bytes()).get('sequence')==data['subversion']:started=True
    if started:core_command(candidate,'rollback')


def discard_partial_backup(old):
    root=installer.app_directory().with_name('TailD.rollback')
    if not root.exists():return
    # A failed first backup has no valid signature file yet. Its exact old
    # signed inventory still binds every eligible member; unknown/changed files
    # cause refusal before deletion, rather than a recursive cleanup.
    allowed={row['path']:row for row in old['files']}
    paths=[]
    for path in root.rglob('*'):
        manifest.ordinary(path)
        if path.is_dir():continue
        name=path.relative_to(root).as_posix()
        if name in (manifest.MANIFEST,manifest.SIGNATURE,'installation.json'):paths.append(path);continue
        row=allowed.get(name)
        if row is None:raise manifest.PackageError('unknown-partial-backup-member')
        with path.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
        if digest!=row['sha256']:raise manifest.PackageError('changed-partial-backup-member')
        paths.append(path)
    for path in paths:path.unlink()
    for path in sorted((p for p in root.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):path.rmdir()
    root.rmdir()


def recover(candidate):
    manifest.verify(candidate)
    journal=read_journal()
    if journal is None or journal['phase'] in ('complete','recovered'):return
    new=journal_manifest(journal,'new');app=installer.app_directory()
    old=journal_manifest(journal,'old') if journal.get('old_manifest') else None
    if journal['phase'] in ('core_started','core_complete'):
        rollback_core(candidate,journal)
        journal['phase']='core_restored';write_journal(journal)
    # Before extraction a partial backup is expendable only if the entire
    # unchanged original installation still verifies independently.
    if journal['phase']=='preparing' and old is not None and manifest.verify(app,installed=True)==old:
        discard_partial_backup(old)
        installer.reader_start(app,journal['owner_sid'])
    elif old is not None:
        installer.rollback(data=new)
    else:
        installer.abort(candidate,data=new)
    journal['phase']='recovered';write_journal(journal)


def prepare(candidate,owner,local_data):
    data=manifest.verify(candidate)
    if data['schema']!='taild-package-v2':raise manifest.PackageError('complete-product-package-required')
    recover(candidate)
    app=installer.app_directory()
    if app.exists():
        current=manifest.verify(app,installed=True);manifest.newer(data,current)
        config=json.loads((app/'installation.json').read_bytes())
        if owner!=config['owner_sid']:raise manifest.PackageError('different-owner-requires-explicit-migration')
        if data['subversion']<=config.get('highest_subversion',current['subversion']):raise manifest.PackageError('replay-after-rollback')
    else:current=None
    journal={'schema':'taild-setup-transaction-v1','phase':'preparing','owner_sid':owner,'local_data':local_data}
    record_manifest(journal,'new',candidate)
    if current:record_manifest(journal,'old',app)
    write_journal(journal)
    installer.prepare(candidate,owner)
    journal['phase']='prepared';write_journal(journal)
    return data


def finish(candidate):
    candidate_data=manifest.verify(candidate);app=installer.app_directory()
    installed=manifest.verify(app,installed=True);journal=read_journal()
    if journal is None or installed!=candidate_data or journal_manifest(journal,'new')!=installed:
        raise manifest.PackageError('installation-journal-mismatch')
    journal['phase']='core_started';write_journal(journal)
    active=state_directory()/'deployment-v4.json'
    core_command(candidate,'update' if active.exists() else 'install')
    journal['phase']='core_complete';write_journal(journal)
    config=app/'installation.json'
    if config.exists():metadata=json.loads(config.read_bytes())
    else:metadata={'schema':'taild-installation-v1','owner_sid':journal['owner_sid']}
    metadata['local_data']=journal['local_data'];metadata['highest_subversion']=max(metadata.get('highest_subversion',0),installed['subversion'])
    installer.write_metadata(config,metadata)
    installer.reader_start(app,journal['owner_sid'])
    # Restore the user's existing update preference after the initial core
    # migration temporarily disables update application. This installation's
    # explicitly selected channel is now TailD, not TailDNS or official MSI.
    record=json.loads(active.read_bytes())
    cli=app.parent/'tailscale.exe'
    result=subprocess.run([str(cli),'set','--auto-update='+str(bool(record['originalAutoUpdateApply'])).lower()],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise manifest.PackageError('update-preference-restore-failed')
    core_command(candidate,'resume-analytics')
    journal['phase']='complete';write_journal(journal)


def rollback(candidate):
    manifest.verify(candidate);journal=read_journal()
    if journal is None or journal['phase']!='complete':raise manifest.PackageError('completed-installation-required')
    journal['phase']='core_complete';write_journal(journal)
    recover(candidate)
