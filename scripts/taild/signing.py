"""Dedicated local release-manifest identity; never a Control D credential.

Only the owning Windows vault persists private bytes. CI provision/publication is
not performed by this command. Manifest signatures are not Authenticode.
"""
import argparse
import base64
import json
from pathlib import Path

TARGET='Darkaxt/TailD/ReleaseManifest/Ed25519/v1'


def private_key(create=False):
    import win32cred,pywintypes
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    try:
        stored=win32cred.CredRead(TARGET,win32cred.CRED_TYPE_GENERIC)['CredentialBlob']
        value=base64.b64decode(stored.decode('utf-16-le') if isinstance(stored,bytes) else stored,validate=True)
    except pywintypes.error as error:
        if error.winerror!=1168 or not create:raise RuntimeError('Signing identity unavailable') from None
        key=Ed25519PrivateKey.generate();value=key.private_bytes_raw()
        win32cred.CredWrite({'Type':win32cred.CRED_TYPE_GENERIC,'TargetName':TARGET,
            'CredentialBlob':base64.b64encode(value).decode(),'Persist':win32cred.CRED_PERSIST_LOCAL_MACHINE,
            'UserName':'TailD manifest signing','Comment':'Dedicated TailD Ed25519 signing key; not Authenticode'})
    if not isinstance(value,bytes) or len(value)!=32:raise RuntimeError('Invalid signing identity')
    return Ed25519PrivateKey.from_private_bytes(value)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('provision','public','sign','make','core','release'))
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--package',type=Path);parser.add_argument('--provenance',type=Path)
    parser.add_argument('--core-version-file',type=Path);parser.add_argument('--subversion',type=int)
    args=parser.parse_args();key=private_key(args.operation=='provision')
    if args.operation in ('core','release'):
        import package_manifest as contract
        if base64.b64encode(key.public_key().public_bytes_raw()).decode()!=contract.PUBLIC_KEY:
            raise RuntimeError('Signing identity does not match the pinned production key')
        if args.operation=='core':
            import core_manifest
            raw=core_manifest.make(args.package,args.provenance,args.subversion)
            existing=args.package/'taildns-windows-update.json'
            if existing.exists():
                if existing.read_bytes()!=raw:raise RuntimeError('Connectivity manifest mismatch')
            else:
                with existing.open('xb') as f:f.write(raw)
            with (args.package/'taildns-windows-update.json.sig').open('xb') as f:f.write(base64.b64encode(key.sign(raw)))
        else:
            import release_channel
            data=release_channel.validate(json.loads(args.manifest.read_bytes()))
            with args.manifest.with_suffix('.json.sig').open('xb') as f:f.write(key.sign(args.manifest.read_bytes()))
        print(json.dumps({'state':'signed-'+args.operation,'authenticode':False}))
        return
    if args.operation=='make':
        import package_manifest as contract
        if not all((args.package,args.provenance,args.core_version_file,args.subversion)):
            parser.error('Package, provenance, actual pinned-core VERSION.txt and subversion required')
        provenance=json.loads(args.provenance.read_text(encoding='utf-8'))
        if provenance['source_dirty']:raise RuntimeError('Commit the candidate before signing; no dirty-source release identity')
        upstream=args.core_version_file.read_text().strip()
        if base64.b64encode(key.public_key().public_bytes_raw()).decode()!=contract.PUBLIC_KEY:
            raise RuntimeError('Signing identity does not match the pinned production key')
        members=contract.inventory(args.package)
        builder_members=members
        if provenance.get('connectivity'):
            import core_manifest
            core_manifest.verify(args.package/'connectivity',contract.PUBLIC_KEY)
            builder_members=[row for row in members if row['path']!='connectivity/taildns-windows-update.json.sig']
        if (provenance.get('fixture_trust') is not False or provenance.get('upstream_version')!=upstream
            or provenance.get('subversion')!=args.subversion or sorted(provenance.get('files',[]),key=lambda row:row['path'])!=builder_members):
            raise RuntimeError('Build provenance does not match the production payload/version')
        data=contract.validate({'schema':'taild-package-v2' if provenance.get('connectivity') else 'taild-package-v1','product':'TailD','upstream_version':upstream,
            'subversion':args.subversion,'version':upstream+'+'+str(args.subversion),
            'architecture':'windows-amd64','source_commit':provenance['source_commit'],
            'core_replace':provenance['core_replace'],'history_schema':4,
            'authenticode':'not-signed','files':members})
        raw=json.dumps(data,sort_keys=True,separators=(',',':')).encode()
        with (args.package/contract.MANIFEST).open('xb') as f:f.write(raw)
        with (args.package/contract.SIGNATURE).open('xb') as f:f.write(key.sign(raw))
        print(json.dumps({'state':'signed-local-package','version':data['version'],'authenticode':False}))
        return
    if args.operation=='sign':
        if not args.manifest or args.manifest.stat().st_size>2*1024*1024:parser.error('Bounded manifest required')
        with args.manifest.with_suffix(args.manifest.suffix+'.sig').open('xb') as f:
            f.write(key.sign(args.manifest.read_bytes()))
        print(json.dumps({'state':'signed','authenticode':False}))
    else:
        print(json.dumps({'public_key_base64':base64.b64encode(key.public_key().public_bytes_raw()).decode(),
            'private_key_storage':'owning-user Windows vault','github_secret_created':False}))


if __name__=='__main__':main()
