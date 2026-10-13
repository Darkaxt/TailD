"""Signed TailD channel, bounded transport and interrupted staging contracts."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import unittest
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import release_channel as channel


class ReleaseChannelTest(unittest.TestCase):
    def setUp(self):
        base=os.environ.get('TAILD_PACKAGE_TEST_OUTPUT')
        if not base:raise RuntimeError('Use an explicitly owned test output directory')
        self.root=Path(base)/uuid.uuid4().hex;self.root.mkdir(parents=True)
        self.key=Ed25519PrivateKey.generate()
        self.public=base64.b64encode(self.key.public_key().public_bytes_raw()).decode()
        self.installer=b'MZ synthetic installer; never executed'
        self.data={'schema':'taild-release-v1','product':'TailD','version':'1.105.0+2',
            'upstream_version':'1.105.0','subversion':2,'architecture':'windows-amd64',
            'source_commit':'a'*40,'core_replace':'replace tailscale.com => github.com/Darkaxt/tailscale v1.103.0-pre.0.20261013063423-de6111f507ae',
            'history_schema':4,'package_sha256':'b'*64,'authenticode':'not-signed',
            'installer':{'name':'TailD-1.105.0+2-windows-amd64-setup.exe',
                'size':len(self.installer),'sha256':hashlib.sha256(self.installer).hexdigest()}}

    def signed(self,data=None):
        raw=json.dumps(data or self.data,sort_keys=True,separators=(',',':')).encode()
        return raw,self.key.sign(raw)

    def test_independent_signature_identity_and_global_sequence_floor(self):
        raw,sig=self.signed()
        self.assertEqual(channel.verify(raw,sig,1,'1.104.1',self.public),self.data)
        for floor,base in ((2,'1.105.0'),(3,'1.104.1'),(1,'1.106.0')):
            with self.subTest(floor=floor,base=base),self.assertRaises(channel.ChannelError):
                channel.verify(raw,sig,floor,base,self.public)
        with self.assertRaises(channel.ChannelError):channel.verify(raw+b' ',sig,1,'1.105.0',self.public)
        with self.assertRaises(channel.ChannelError):channel.verify(raw,sig,1,'1.105.0',base64.b64encode(bytes(32)).decode())

    def test_signed_malformed_envelopes_are_rejected(self):
        cases=({'subversion':True},{'version':'1.106.0+2'},{'architecture':'windows-arm64'},
            {'history_schema':5},{'authenticode':'signed'},{'source_commit':'not-a-commit'},
            {'extra':'untrusted'},{'installer':{**self.data['installer'],'name':'../setup.exe'}},
            {'installer':{**self.data['installer'],'size':2**32}})
        for change in cases:
            raw,sig=self.signed({**self.data,**change})
            with self.subTest(change=change),self.assertRaises(channel.ChannelError):
                channel.verify(raw,sig,1,'1.105.0',self.public)
        raw,sig=self.signed();raw=raw[:-1]+b',"product":"TailD"}'
        with self.assertRaises(channel.ChannelError):channel.verify(raw,self.key.sign(raw),1,'1.105.0',self.public)

    def test_release_metadata_cannot_substitute_other_repos_or_tags(self):
        name=self.data['installer']['name']
        good='https://github.com/Darkaxt/TailD/releases/download/windows-v1.105.0%2B2/'+name.replace('+','%2B')
        metadata={'draft':False,'prerelease':False,'tag_name':'windows-v1.105.0+2',
            'assets':[{'name':n,'browser_download_url':good.rsplit('/',1)[0]+'/'+n.replace('+','%2B')}
                for n in (name,channel.ENVELOPE,channel.SIGNATURE)]}
        self.assertEqual(channel.assets(metadata,self.data)[name],good)
        for changed in ({'draft':True},{'prerelease':True},{'tag_name':'windows-v1.105.0+3'},
            {'assets':metadata['assets']+metadata['assets'][:1]},
            {'assets':[{**a,'browser_download_url':a['browser_download_url'].replace('/TailD/','/tailscale/')} for a in metadata['assets']]}):
            with self.subTest(changed=changed),self.assertRaises(channel.ChannelError):
                channel.assets({**metadata,**changed},self.data)

    def test_partial_download_never_becomes_an_executable_and_retry_is_explicit(self):
        class Interrupted(io.BytesIO):
            def read(self,size=-1):
                if self.tell():raise OSError('synthetic connection interruption')
                return super().read(8)
        with self.assertRaises(OSError):channel.stage(Interrupted(self.installer),self.root,self.data)
        final=self.root/self.data['installer']['name']
        self.assertFalse(final.exists())
        self.assertTrue(final.with_suffix('.exe.partial').exists())
        self.assertEqual(channel.stage(io.BytesIO(self.installer),self.root,self.data),final)
        self.assertEqual(final.read_bytes(),self.installer)
        with self.assertRaises(channel.ChannelError):channel.stage(io.BytesIO(self.installer),self.root,self.data)

    def test_wrong_size_hash_and_extra_bytes_never_publish_staging(self):
        for content in (self.installer[:-1],self.installer+b'x',b'x'*len(self.installer)):
            root=self.root/uuid.uuid4().hex;root.mkdir()
            with self.subTest(content=content),self.assertRaises(channel.ChannelError):
                channel.stage(io.BytesIO(content),root,self.data)
            self.assertFalse((root/self.data['installer']['name']).exists())


if __name__=='__main__':unittest.main()
