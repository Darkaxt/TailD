"""Protected CI signing tooling; never executes/imports the candidate payload.

The release workflow pins this tooling to its reviewed commit independently of
the build revision. Production seed is consumed from the protected environment,
not copied into the candidate, filesystem, arguments, logs or published output.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

import core_manifest
import package_manifest as contract
import release_channel


def identity(key):
    if base64.b64encode(key.public_key().public_bytes_raw()).decode()!=contract.PUBLIC_KEY:
        raise ValueError('Protected signer does not match the reviewed public pin')


def sign_package(key,build,expected_source,sequence):
    identity(key);build=Path(build)
    provenance=json.loads((build/'provenance.json').read_bytes())
    package=build/'payload'/'TailD'
    if (provenance.get('source_commit')!=expected_source or provenance.get('source_dirty') is not False or
        provenance.get('fixture_trust') is not False or provenance.get('connectivity') is not True or
        provenance.get('subversion')!=sequence or provenance.get('architecture')!='windows-amd64' or
        provenance.get('upstream_version')!='1.105.0' or
        provenance.get('core_replace')!='replace tailscale.com => github.com/Darkaxt/tailscale '+core_manifest.CORE_MODULE):
        raise ValueError('Release build identity is not the selected clean production source')
    if contract.inventory(package)!=sorted(provenance['files'],key=lambda row:row['path']):
        raise ValueError('Unsigned build inventory mismatch')
    core=package/'connectivity';core_provenance=json.loads((core/'core-provenance.json').read_bytes())
    if core_provenance['source_commit']!=expected_source:raise ValueError('Core overlay source mismatch')
    raw=core_manifest.make(core,core/'core-provenance.json',sequence)
    if (core/'taildns-windows-update.json').read_bytes()!=raw:raise ValueError('Core manifest mismatch')
    with (core/'taildns-windows-update.json.sig').open('xb') as output:output.write(base64.b64encode(key.sign(raw)))
    core_manifest.verify(core,contract.PUBLIC_KEY)
    data=contract.validate({'schema':'taild-package-v2','product':'TailD','upstream_version':provenance['upstream_version'],
        'subversion':sequence,'version':provenance['upstream_version']+'+'+str(sequence),
        'architecture':'windows-amd64','source_commit':expected_source,'core_replace':provenance['core_replace'],
        'history_schema':4,'authenticode':'not-signed','files':contract.inventory(package)})
    raw=json.dumps(data,sort_keys=True,separators=(',',':')).encode()
    with (package/contract.MANIFEST).open('xb') as output:output.write(raw)
    with (package/contract.SIGNATURE).open('xb') as output:output.write(key.sign(raw))
    contract.verify(package)
    return data


def sign_installer(key,root,expected_source,sequence):
    identity(key);root=Path(root)
    raw=(root/contract.MANIFEST).read_bytes()
    data=contract.verify_bytes(raw,(root/contract.SIGNATURE).read_bytes())
    if data['schema']!='taild-package-v2' or data['source_commit']!=expected_source or data['subversion']!=sequence:
        raise ValueError('Installer source mismatch')
    name='TailD-'+data['version']+'-windows-amd64-setup.exe'
    path=root/name;contract.ordinary(path)
    with path.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
    envelope=release_channel.validate({'schema':'taild-release-v1','product':'TailD','upstream_version':data['upstream_version'],
        'subversion':sequence,'version':data['version'],'architecture':'windows-amd64','source_commit':expected_source,
        'core_replace':data['core_replace'],'history_schema':4,'authenticode':'not-signed',
        'package_sha256':hashlib.sha256(raw).hexdigest(),'installer':{'name':name,'size':path.stat().st_size,'sha256':digest}})
    raw=json.dumps(envelope,sort_keys=True,separators=(',',':')).encode()
    with (root/release_channel.ENVELOPE).open('xb') as output:output.write(raw)
    with (root/release_channel.SIGNATURE).open('xb') as output:output.write(key.sign(raw))
    return envelope


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('package','installer'))
    parser.add_argument('--root',required=True,type=Path);parser.add_argument('--source',required=True)
    parser.add_argument('--sequence',required=True,type=int)
    args=parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise RuntimeError('Protected hosted signer required; use the owning-user vault for local signing')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    seed=base64.b64decode(os.environ.pop('TAILD_MANIFEST_SIGNING_SEED_BASE64'),validate=True)
    key=Ed25519PrivateKey.from_private_bytes(seed)
    data=(sign_package if args.operation=='package' else sign_installer)(key,args.root,args.source,args.sequence)
    print(json.dumps({'state':'signed-'+args.operation,'version':data['version'],'source_commit':data['source_commit'],'authenticode':False}))


if __name__=='__main__':main()
