"""Credential-free protected-signer contract, using an ephemeral test key only."""
import base64
import hashlib
import json
import os
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import core_manifest
import package_manifest as manifest
import release_channel
import release_signer


class SignerTest(unittest.TestCase):
    def setUp(self):
        self.root=Path(os.environ['TAILD_PACKAGE_TEST_OUTPUT'])/uuid.uuid4().hex;self.root.mkdir(parents=True)
        self.key=Ed25519PrivateKey.generate();self.public=base64.b64encode(self.key.public_key().public_bytes_raw()).decode()
        self.enterContext(patch.object(manifest,'PUBLIC_KEY',self.public))

    def build(self):
        package=self.root/'payload'/'TailD';package.mkdir(parents=True)
        for name in ('TailD.exe','TailD.Background.exe','TailD.Setup.exe','desktop/TailD.Desktop.exe','desktop/ui/index.html',
            '_internal/python314.dll','desktop/licenses/frontend-GPL-3.0.txt','desktop/licenses/frontend-dependencies.txt',
            'licenses/runtime-license-inventory.json',*['connectivity/'+n for n in core_manifest.NAMES],
            'connectivity/inherited-core-LICENSE.txt'):
            path=package/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(('synthetic '+name).encode())
        core=package/'connectivity'
        provenance={'schema':'taild-core-build-v1','core_commit':core_manifest.CORE,'core_module':core_manifest.CORE_MODULE,
            'source_commit':'a'*40,'source_dirty':False,'upstream_version':'1.105.0','subversion':1,
            'module_sum':core_manifest.CORE_SUM}
        (core/'core-provenance.json').write_text(json.dumps(provenance))
        (core/'taildns-windows-update.json').write_bytes(core_manifest.make(core,core/'core-provenance.json',1))
        provenance={'source_commit':'a'*40,'source_dirty':False,'fixture_trust':False,'connectivity':True,
            'subversion':1,'architecture':'windows-amd64','upstream_version':'1.105.0',
            'core_replace':'replace tailscale.com => github.com/Darkaxt/tailscale '+core_manifest.CORE_MODULE,
            'files':manifest.inventory(package)}
        (self.root/'provenance.json').write_text(json.dumps(provenance))
        return package

    def test_full_package_and_installer_signatures_bind_one_selected_source(self):
        package=self.build()
        data=release_signer.sign_package(self.key,self.root,'a'*40,1)
        self.assertEqual(manifest.verify(package),data)
        core_manifest.verify(package/'connectivity',self.public)
        name='TailD-1.105.0+1-windows-amd64-setup.exe'
        (self.root/name).write_bytes(b'MZ synthetic installer')
        for item in (manifest.MANIFEST,manifest.SIGNATURE):(self.root/item).write_bytes((package/item).read_bytes())
        envelope=release_signer.sign_installer(self.key,self.root,'a'*40,1)
        self.assertEqual(release_channel.verify((self.root/release_channel.ENVELOPE).read_bytes(),
            (self.root/release_channel.SIGNATURE).read_bytes(),0,'1.105.0',self.public),envelope)
        self.assertEqual(envelope['installer']['sha256'],hashlib.sha256((self.root/name).read_bytes()).hexdigest())

    def test_mismatched_source_or_tampered_build_is_not_signed(self):
        package=self.build()
        with self.assertRaises(ValueError):release_signer.sign_package(self.key,self.root,'b'*40,1)
        (package/'TailD.exe').write_bytes(b'TAMPERED')
        with self.assertRaises(ValueError):release_signer.sign_package(self.key,self.root,'a'*40,1)
        self.assertFalse((package/manifest.SIGNATURE).exists())
        self.assertFalse((package/'connectivity'/'taildns-windows-update.json.sig').exists())

    def test_source_core_pin_mismatch_is_not_signed(self):
        package=self.build()
        path=self.root/'provenance.json';data=json.loads(path.read_bytes())
        data['core_replace']='replace tailscale.com => github.com/Darkaxt/tailscale v1.103.0-pre.0.20261013063423-de6111f507ae'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'identity'):
            release_signer.sign_package(self.key,self.root,'a'*40,1)
        self.assertFalse((package/manifest.SIGNATURE).exists())


if __name__=='__main__':unittest.main()
