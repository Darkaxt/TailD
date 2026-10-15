"""Complete signed-file migration/recovery with the external SCM boundary isolated."""
import base64
import json
import os
from pathlib import Path
import shutil
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import delivery
import installer
import package_manifest as manifest


class DeliveryTest(unittest.TestCase):
    def setUp(self):
        self.root=Path(os.environ['TAILD_PACKAGE_TEST_OUTPUT'])/uuid.uuid4().hex
        self.root.mkdir(parents=True);self.app=self.root/'installed';self.state=self.root/'state';self.state.mkdir()
        self.key=Ed25519PrivateKey.generate();self.public=base64.b64encode(self.key.public_key().public_bytes_raw()).decode()
        self.owner='S-1-5-21-1000';self.local=self.root/'local'
        self.enterContext(patch.object(manifest,'PUBLIC_KEY',self.public))
        self.enterContext(patch.object(installer,'app_directory',return_value=self.app))
        self.enterContext(patch.object(delivery,'state_directory',return_value=self.state))
        for name in ('ensure_quiescent','reader_stop','reader_start','update_registration'):
            self.enterContext(patch.object(installer,name,return_value=False))

    def candidate(self,sequence,*,schema='taild-package-v2'):
        root=self.root/('candidate-'+str(sequence));root.mkdir()
        names=['TailD.exe','TailD.Background.exe','TailD.Setup.exe','desktop/TailD.Desktop.exe','desktop/ui/index.html',
            '_internal/python314.dll','desktop/licenses/frontend-GPL-3.0.txt',
            'desktop/licenses/frontend-dependencies.txt','licenses/runtime-license-inventory.json']
        names+=['connectivity/'+n for n in ('taildnsd.exe','tailscale.exe','taildns.exe','taildns-ipn.exe',
            'taildns-installer.exe','taildns-windows-update.json','taildns-windows-update.json.sig',
            'inherited-core-LICENSE.txt','core-provenance.json')]
        for name in names:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(('synthetic '+name+str(sequence)).encode())
        data={'schema':schema,'product':'TailD','upstream_version':'1.105.0','subversion':sequence,
            'version':'1.105.0+'+str(sequence),'architecture':'windows-amd64','source_commit':'a'*40,
            'core_replace':'replace tailscale.com => github.com/Darkaxt/tailscale v1.103.0-pre.0.20261013063423-de6111f507ae',
            'history_schema':4,'authenticode':'not-signed','files':manifest.inventory(root)}
        raw=json.dumps(data,sort_keys=True,separators=(',',':')).encode()
        (root/manifest.MANIFEST).write_bytes(raw);(root/manifest.SIGNATURE).write_bytes(self.key.sign(raw))
        return root,data

    def installed(self,source):
        shutil.copytree(source,self.app)
        (self.app/'installation.json').write_text(json.dumps({'schema':'taild-installation-v1',
            'owner_sid':self.owner,'local_data':str(self.local),'highest_subversion':1}))

    @unittest.skipUnless(os.name=='nt','Windows setup owner boundary')
    def test_v1_upgrade_uses_explicit_original_owner_location_before_v2_transaction(self):
        import updater
        old,_=self.candidate(1,schema='taild-package-v1');new,_=self.candidate(2);self.installed(old)
        (self.app/'installation.json').write_text(json.dumps({'schema':'taild-installation-v1','owner_sid':self.owner,'highest_subversion':1}))
        owner_file=self.root/'owner.json';owner_file.write_text(json.dumps({'owner_sid':self.owner,'local_data':str(self.local)}))
        with patch.object(installer.ctypes.windll.shell32,'IsUserAnAdmin',return_value=True),patch.object(updater,'graceful_stop') as stop:
            installer.main(['prepare','--candidate',str(new),'--owner-file',str(owner_file)])
        stop.assert_called_once_with({'owner_sid':self.owner,'local_data':str(self.local)})
        self.assertEqual(delivery.read_journal()['phase'],'prepared')
        self.assertEqual(delivery.read_journal()['local_data'],str(self.local))
        self.assertEqual(manifest.verify(self.app.with_name('TailD.rollback'),installed=True)['schema'],'taild-package-v1')

    @unittest.skipUnless(os.name=='nt','Windows setup owner boundary')
    def test_v1_upgrade_refuses_different_original_owner_before_stopping_any_process(self):
        import updater
        old,_=self.candidate(1,schema='taild-package-v1');new,_=self.candidate(2);self.installed(old)
        (self.app/'installation.json').write_text(json.dumps({'schema':'taild-installation-v1','owner_sid':self.owner,'highest_subversion':1}))
        owner_file=self.root/'owner.json';owner_file.write_text(json.dumps({'owner_sid':'S-1-5-21-2000','local_data':str(self.local)}))
        with patch.object(installer.ctypes.windll.shell32,'IsUserAnAdmin',return_value=True),patch.object(updater,'graceful_stop') as stop:
            with self.assertRaises(manifest.PackageError):installer.main(['prepare','--candidate',str(new),'--owner-file',str(owner_file)])
        stop.assert_not_called();self.assertIsNone(delivery.read_journal())
        self.assertEqual(manifest.verify(self.app,installed=True)['schema'],'taild-package-v1')

    def test_interruption_after_core_activation_restores_previous_payload_and_floor(self):
        old,_=self.candidate(1);new,newdata=self.candidate(2);self.installed(old)
        delivery.prepare(new,self.owner,str(self.local))
        shutil.copytree(new,self.app,dirs_exist_ok=True)
        journal=delivery.read_journal();journal['phase']='core_started';delivery.write_journal(journal)
        calls=[]
        with patch.object(delivery,'rollback_core',side_effect=lambda *a:calls.append('core-restored')):
            delivery.recover(new)
        self.assertEqual(calls,['core-restored'])
        self.assertEqual(manifest.verify(self.app,installed=True)['subversion'],1)
        self.assertEqual(json.loads((self.app/'installation.json').read_text())['highest_subversion'],2)
        self.assertEqual(delivery.read_journal()['phase'],'recovered')
        with self.assertRaisesRegex(manifest.PackageError,'replay'):
            delivery.prepare(new,self.owner,str(self.local))

    def test_journal_signature_tamper_cannot_drive_recovery(self):
        old,_=self.candidate(1);new,_=self.candidate(2);self.installed(old)
        delivery.prepare(new,self.owner,str(self.local))
        journal=delivery.read_journal();journal['new_manifest']=base64.b64encode(b'{}').decode();delivery.write_journal(journal)
        before=(self.app/'TailD.exe').read_bytes()
        with self.assertRaises(manifest.PackageError):delivery.recover(new)
        self.assertEqual((self.app/'TailD.exe').read_bytes(),before)

    def test_product_uninstall_returns_core_before_reader_removal(self):
        source,_=self.candidate(1);self.installed(source);actions=[]
        with patch.object(delivery,'core_command',side_effect=lambda _,action:actions.append(action)),\
             patch.object(installer,'reader_stop',side_effect=lambda **kw:actions.append('reader-removed')):
            installer.uninstall(False)
        self.assertEqual(actions,['unmigrate','reader-removed'])

    def test_failed_core_unmigration_leaves_reader_and_history_intact(self):
        source,_=self.candidate(1);self.installed(source)
        with patch.object(delivery,'core_command',side_effect=manifest.PackageError('synthetic-core-failure')),\
             patch.object(installer,'remove_history') as delete,patch.object(installer,'reader_stop') as stop,\
             self.assertRaisesRegex(manifest.PackageError,'synthetic-core-failure'):
            installer.uninstall(True)
        delete.assert_called_once_with(dry_run=True);stop.assert_not_called()

    def test_initial_migration_rollback_uses_normal_uninstall_and_keeps_history(self):
        new,_=self.candidate(1);self.installed(new)
        journal={'schema':'taild-setup-transaction-v1','phase':'complete','owner_sid':self.owner,'local_data':str(self.local)}
        delivery.record_manifest(journal,'new',new);delivery.write_journal(journal)
        with patch.object(delivery.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as process,\
             patch.object(delivery.subprocess,'CREATE_NO_WINDOW',0,create=True):
            delivery.rollback(new)
        command=process.call_args.args[0]
        self.assertEqual(command[0],str(self.app/'unins000.exe'))
        self.assertNotIn('--delete-history',command)
        self.assertEqual(delivery.read_journal()['phase'],'recovered')

    def test_failed_first_migration_removes_framework_with_normal_uninstaller(self):
        new,_=self.candidate(1)
        delivery.prepare(new,self.owner,str(self.local))
        shutil.copytree(new,self.app,dirs_exist_ok=True)
        framework=self.app/'unins000.exe';framework.write_bytes(b'synthetic framework')
        journal=delivery.read_journal();journal['phase']='core_started';delivery.write_journal(journal)
        actions=[]
        def uninstall(command,**options):
            self.assertEqual(delivery.read_journal()['phase'],'core_restored')
            self.assertEqual(command[0],str(framework));actions.append('framework-uninstall')
            framework.unlink()
            return SimpleNamespace(returncode=0)
        with patch.object(delivery,'rollback_core',side_effect=lambda *a:actions.append('core-restored')),\
             patch.object(delivery.subprocess,'run',side_effect=uninstall),\
             patch.object(delivery,'initial_framework_remaining',side_effect=lambda:framework.exists()),\
             patch.object(delivery.subprocess,'CREATE_NO_WINDOW',0,create=True):
            delivery.recover(new)
        self.assertEqual(actions,['core-restored','framework-uninstall'])
        self.assertFalse(self.app.exists())
        self.assertEqual(delivery.read_journal()['phase'],'recovered')

    def test_first_recovery_uninstall_accepts_verified_partial_files_without_unmigrating_again(self):
        new,data=self.candidate(1);self.installed(new)
        journal={'schema':'taild-setup-transaction-v1','phase':'core_restored','owner_sid':self.owner,'local_data':str(self.local)}
        delivery.record_manifest(journal,'new',new);delivery.write_journal(journal)
        (self.app/'TailD.exe').unlink() # Interrupted normal uninstall; retained members must still verify.
        with patch.object(delivery,'core_command') as core,patch.object(installer,'reader_stop') as stop:
            installer.uninstall(False)
        core.assert_not_called();stop.assert_called_once_with(remove=True)
        (self.app/'TailD.Background.exe').write_bytes(b'tampered')
        with self.assertRaises(manifest.PackageError):installer.uninstall(False)

    def test_update_does_not_reapply_original_migration_update_preference(self):
        new,_=self.candidate(2);self.installed(new)
        journal={'schema':'taild-setup-transaction-v1','phase':'prepared','owner_sid':self.owner,'local_data':str(self.local)}
        delivery.record_manifest(journal,'new',new);delivery.write_journal(journal)
        (self.state/'deployment-v4.json').write_text(json.dumps({'originalAutoUpdateApply':False}))
        with patch.object(delivery,'core_command',return_value={}) as core,\
             patch.object(delivery.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as process,\
             patch.object(delivery.subprocess,'CREATE_NO_WINDOW',0,create=True):
            delivery.finish(new)
        self.assertEqual([call.args[1] for call in core.call_args_list],['update','resume-analytics'])
        process.assert_not_called() # Core update preserves the current preference itself.


if __name__=='__main__':unittest.main()
