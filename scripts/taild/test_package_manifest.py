"""Signed-package/replay/path and exact-member recovery contracts."""
import base64
import json
import os
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import package_manifest as manifest
import installer
import signing
import sys


class PackageManifestTest(unittest.TestCase):
    def test_service_notifications_exclude_current_state(self):
        for state in range(1,8):
            mask=installer.notification_mask(state)
            self.assertEqual(mask & (1 << (state-1)),0)
            self.assertEqual(mask | (1 << (state-1)),0x7f)

    def test_production_signing_rejects_changed_build_provenance(self):
        for name in (manifest.MANIFEST,manifest.SIGNATURE):(self.root/name).unlink()
        provenance=self.root.with_name(self.root.name+'-provenance.json')
        version=self.root.with_name(self.root.name+'-VERSION.txt');version.write_text('1.105.0')
        provenance.write_text(json.dumps({'source_dirty':False,'fixture_trust':False,
            'upstream_version':'1.105.0','subversion':1,'source_commit':'a'*40,
            'core_replace':self.data['core_replace'],'files':[]}))
        args=['signing.py','make','--package',str(self.root),'--provenance',str(provenance),
            '--core-version-file',str(version),'--subversion','1']
        with patch.object(signing,'private_key',return_value=self.key),patch.object(manifest,'PUBLIC_KEY',self.public),\
             patch.object(sys,'argv',args),self.assertRaisesRegex(RuntimeError,'provenance'):
            signing.main()

    def test_uninstall_confirmation_is_nondestructive(self):
        source=(Path(__file__).resolve().parents[2]/'desktop/installer.iss').read_text()
        initialize=source.split('function InitializeUninstall: Boolean;',1)[1].split('procedure ',1)[0]
        self.assertNotIn("'uninstall'",initialize)
        self.assertNotIn("'remove-history'",initialize)
        self.assertIn("'check-uninstall'",initialize)
        self.assertIn('CurUninstallStep = usUninstall',source)

    def test_rollback_refuses_to_overwrite_its_own_loaded_helper(self):
        with patch.object(installer,'app_directory',return_value=self.root),\
             patch.object(sys,'executable',str(self.root/'TailD.Setup.exe')),\
             self.assertRaisesRegex(manifest.PackageError,'detached'):
            installer.rollback()

    def test_only_actual_uninstall_can_exempt_its_framework_bootstrap(self):
        app=self.root
        self.assertTrue(installer.blocks_installation(app/'unins000.exe',app))
        self.assertFalse(installer.blocks_installation(app/'unins000.exe',app,True))
        for name in ('TailD.exe','TailD.Setup.exe','unins001.exe','desktop/TailD.Desktop.exe'):
            self.assertTrue(installer.blocks_installation(app/name,app,True))
        self.assertFalse(installer.blocks_installation(app.parent/'other.exe',app,True))

    def setUp(self):
        if os.name=='nt':
            base=os.environ.get('TAILD_PACKAGE_TEST_OUTPUT')
            if not base:raise RuntimeError('Set TAILD_PACKAGE_TEST_OUTPUT to a registered task-owned fixture root')
            self.root=Path(base)/uuid.uuid4().hex;self.root.mkdir(parents=True)
        else:
            temp=tempfile.TemporaryDirectory(prefix='taild-package-');self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.key=Ed25519PrivateKey.generate()
        self.public=base64.b64encode(self.key.public_key().public_bytes_raw()).decode()
        for name in ('TailD.exe','TailD.Setup.exe','desktop/TailD.Desktop.exe','desktop/ui/index.html',
            '_internal/python314.dll','desktop/licenses/frontend-GPL-3.0.txt',
            'desktop/licenses/frontend-dependencies.txt','licenses/runtime-license-inventory.json'):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'Synthetic package fixture: '+name.encode())
        self.data={'schema':'taild-package-v1','product':'TailD','upstream_version':'1.105.0','subversion':1,
            'version':'1.105.0+1','architecture':'windows-amd64','source_commit':'a'*40,
            'core_replace':'replace tailscale.com => github.com/Darkaxt/tailscale v1.103.0-pre.0.20261013063423-de6111f507ae',
            'history_schema':4,'authenticode':'not-signed','files':manifest.inventory(self.root)}
        self.sign()

    def sign(self):
        raw=json.dumps(self.data,sort_keys=True,separators=(',',':')).encode()
        (self.root/manifest.MANIFEST).write_bytes(raw);(self.root/manifest.SIGNATURE).write_bytes(self.key.sign(raw))

    def test_signature_is_independent_of_manifest_and_payload(self):
        self.assertEqual(manifest.verify(self.root,self.public),self.data)
        with self.assertRaisesRegex(manifest.PackageError,'signature'):
            manifest.verify(self.root,base64.b64encode(Ed25519PrivateKey.generate().public_key().public_bytes_raw()).decode())
        (self.root/'TailD.exe').write_bytes(b'Tampered')
        with self.assertRaisesRegex(manifest.PackageError,'content-mismatch'):manifest.verify(self.root,self.public)

    def test_manifest_tamper_duplicates_and_noninteger_versions_fail(self):
        (self.root/manifest.MANIFEST).write_bytes(b'{}')
        with self.assertRaisesRegex(manifest.PackageError,'signature'):manifest.verify(self.root,self.public)
        for change in ({'subversion':True},{'version':'1.106.0+1'},{'upstream_version':'1.105.0-pre'},
                       {'architecture':'windows-arm64'},{'authenticode':'signed'},{'history_schema':5}):
            with self.subTest(change=change),self.assertRaises(manifest.PackageError):manifest.validate({**self.data,**change})

    def test_paths_unknown_files_and_required_runtime_are_enforced(self):
        for path in ('../node.key','C:/state','\\server/file','/absolute','a//b','a/./b','a/../b','CON.txt','x.','x ','x:y','a\nb'):
            with self.subTest(path=path),self.assertRaises(manifest.PackageError):manifest.relative_name(path)
        with self.assertRaisesRegex(manifest.PackageError,'incomplete'):
            manifest.validate({**self.data,'files':self.data['files'][:-1]})
        (self.root/'unknown-user-file').write_bytes(b'Preserve, never sweep')
        with self.assertRaisesRegex(manifest.PackageError,'content-mismatch'):manifest.verify(self.root,self.public)

    def test_replay_downgrade_and_pseudoversion_are_not_upgrades(self):
        with self.assertRaisesRegex(manifest.PackageError,'replay'):manifest.newer(self.data,self.data)
        with self.assertRaisesRegex(manifest.PackageError,'downgrade'):
            manifest.newer({**self.data,'subversion':2,'upstream_version':'1.104.9'},self.data)
        manifest.newer({**self.data,'subversion':2},self.data)

    def test_installer_metadata_and_inno_uninstaller_are_not_candidate_payload(self):
        (self.root/'installation.json').write_text('{}')
        with self.assertRaisesRegex(manifest.PackageError,'unexpected-installed'):manifest.verify(self.root,self.public)
        (self.root/'unins000.exe').write_bytes(b'Framework-generated uninstall fixture')
        self.assertEqual(manifest.verify(self.root,self.public,installed=True),self.data)

    def test_exact_member_upgrade_rollback_preserves_external_state_and_watermark(self):
        parent=self.root.with_name(self.root.name+'-installation');parent.mkdir()
        app=parent/'TailD';shutil.copytree(self.root,app)
        (app/'desktop/ui/obsolete.js').write_bytes(b'Old signed asset')
        old={**self.data,'files':manifest.inventory(app)}
        raw=json.dumps(old,sort_keys=True,separators=(',',':')).encode()
        (app/manifest.MANIFEST).write_bytes(raw);(app/manifest.SIGNATURE).write_bytes(self.key.sign(raw))
        metadata={'owner_sid':'S-1-5-21-123','highest_subversion':1}
        (app/'installation.json').write_text(json.dumps(metadata))
        sentinel=parent/'synthetic-node-and-tailnet-lock.state';sentinel.write_bytes(b'Opaque synthetic state; not a real key')
        self.data={**self.data,'version':'1.105.0+2','subversion':2}
        (self.root/'desktop/ui/new.js').write_bytes(b'New signed asset')
        self.data['files']=manifest.inventory(self.root);self.sign()
        verify=manifest.verify
        with patch.object(installer,'app_directory',return_value=app),patch.object(installer,'ensure_quiescent'),\
             patch.object(installer,'reader_stop',return_value=True),patch.object(installer,'reader_start'),patch.object(installer,'update_registration'),\
             patch.object(installer.manifest,'verify',side_effect=lambda root,installed=False:verify(root,self.public,installed)):
            installer.prepare(self.root)
            self.assertFalse((app/'desktop/ui/obsolete.js').exists())
            # Emulate Inno's signed-file extraction; actual SCM/installer exercise
            # is a separate Windows integration criterion, not this unit test.
            for row in self.data['files']:
                target=app/row['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(self.root/row['path'],target)
            for name in (manifest.MANIFEST,manifest.SIGNATURE):shutil.copyfile(self.root/name,app/name)
            (app/'installation.json').write_text(json.dumps({**metadata,'highest_subversion':2}))
            installer.rollback(self.root)
            self.assertTrue((app/'desktop/ui/obsolete.js').exists());self.assertFalse((app/'desktop/ui/new.js').exists())
            self.assertEqual(verify(app,self.public,True)['subversion'],1)
            self.assertEqual(json.loads((app/'installation.json').read_text())['highest_subversion'],2)
            with self.assertRaisesRegex(manifest.PackageError,'replay-after-rollback'):installer.prepare(self.root)
        self.assertEqual(sentinel.read_bytes(),b'Opaque synthetic state; not a real key')


if __name__=='__main__':unittest.main()
