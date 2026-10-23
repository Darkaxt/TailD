"""Static signed inventory for the inherited in-place connectivity installer."""
import hashlib
import json
from pathlib import Path

NAMES=('taildns-installer.exe','taildns-ipn.exe','taildns.exe','taildnsd.exe','tailscale.exe')
CORE='2836228acf7f6b37554d913c8241d294aaf93d24'
CORE_MODULE='v1.103.0-pre.0.20261023053900-2836228acf7f'
CORE_SUM='h1:NrO2tYoOVGVCVH+dTjr/FnJKrDjUE4yfsDUJtk8kyms='


def make(package,provenance,subversion):
    from package_manifest import ordinary
    package=Path(package);provenance=Path(provenance)
    data=json.loads(provenance.read_bytes())
    if (data.get('schema')!='taild-core-build-v1' or data.get('core_commit')!=CORE or
        data.get('source_dirty') is not False or data.get('upstream_version')!='1.105.0' or
        type(subversion) is not int or not 1<=subversion<=65535 or data.get('subversion')!=subversion or
        data.get('core_module')!=CORE_MODULE or data.get('module_sum')!=CORE_SUM):
        raise ValueError('Unverified connectivity source/version')
    rows=[]
    for name in NAMES:
        path=package/name;ordinary(path)
        size=path.stat().st_size
        if not 0<size<256*1024*1024:raise ValueError('Invalid connectivity payload')
        with path.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
        rows.append({'name':name,'sha256':digest,'size':size})
    return json.dumps({'schemaVersion':1,'product':'TailD','upstreamVersion':data['upstream_version'],
        'sequence':subversion,'platform':'windows','arch':'amd64','coreCommit':CORE,'files':rows},
        sort_keys=True,separators=(',',':')).encode()


def verify(package,public_key):
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    package=Path(package);raw=(package/'taildns-windows-update.json').read_bytes()
    expected=make(package,package/'core-provenance.json',json.loads(raw)['sequence'])
    if raw!=expected:raise ValueError('Connectivity manifest/provenance mismatch')
    Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key,validate=True)).verify(
        base64.b64decode((package/'taildns-windows-update.json.sig').read_bytes(),validate=True),raw)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',required=True,type=Path);parser.add_argument('--provenance',required=True,type=Path)
    parser.add_argument('--subversion',required=True,type=int)
    args=parser.parse_args()
    with (args.package/'taildns-windows-update.json').open('xb') as output:output.write(make(args.package,args.provenance,args.subversion))
