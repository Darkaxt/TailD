"""TailD-owned Ed25519 package contract; trust is outside downloaded manifests."""
import base64
import hashlib
import json
from pathlib import Path,PurePosixPath
import re

PUBLIC_KEY='Vq5UrOc4cj4reJmuVdRJ9YFiSRuax9qua/F/WpyW+bE='
MANIFEST='taild-package.json'
SIGNATURE=MANIFEST+'.sig'
METADATA={MANIFEST,SIGNATURE,'installation.json','installation.pending.json'}


class PackageError(ValueError):pass


def relative_name(value):
    if (not isinstance(value,str) or not value or len(value)>240 or '\\' in value or ':' in value
        or any(ord(c)<32 or c in '<>"|?*' for c in value)
        or value.startswith('/') or any(p in ('','.','..') or p.endswith(('.',' ')) for p in value.split('/'))):
        raise PackageError('invalid-package-path')
    for part in PurePosixPath(value).parts:
        if part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
            raise PackageError('invalid-package-path')
    return value


def ordinary(path):
    if path.is_symlink() or getattr(path,'is_junction',lambda:False)() or path.is_file() and path.stat().st_nlink>1:
        raise PackageError('linked-package-member')


def inventory(root,installed=False,expected=None):
    root=Path(root).resolve(strict=True);ordinary(root);rows=[]
    pending=[root]
    while pending:
        directory=pending.pop()
        for path in directory.iterdir():
            ordinary(path)
            if path.is_dir():pending.append(path);continue
            name=path.relative_to(root).as_posix();relative_name(name)
            if name in METADATA:continue
            if installed and name in {'unins000.exe','unins000.dat','unins000.msg'}:continue
            if expected is not None and name not in expected:raise PackageError('package-content-mismatch')
            if len(rows)>=10000 or path.stat().st_size>2**31:raise PackageError('package-resource-limit')
            with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            rows.append({'path':name,'size':path.stat().st_size,'sha256':digest})
    if len(rows)>10000:raise PackageError('package-resource-limit')
    return sorted(rows,key=lambda r:r['path'])


def validate(data):
    required={'schema','product','upstream_version','subversion','version','architecture','source_commit','core_replace','history_schema','files','authenticode'}
    if not isinstance(data,dict) or set(data)!=required:raise PackageError('invalid-package-manifest')
    if data['schema']!='taild-package-v1' or data['product']!='TailD' or data['architecture']!='windows-amd64' or data['history_schema']!=4:
        raise PackageError('incompatible-package')
    if not isinstance(data['upstream_version'],str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',data['upstream_version']):
        raise PackageError('invalid-upstream-version')
    if type(data['subversion']) is not int or not 1<=data['subversion']<2**31 or data['version']!=data['upstream_version']+'+'+str(data['subversion']):
        raise PackageError('invalid-fork-version')
    if not isinstance(data['source_commit'],str) or not re.fullmatch('[0-9a-f]{40}',data['source_commit']):raise PackageError('invalid-source-commit')
    if not isinstance(data['core_replace'],str) or not re.fullmatch(r'replace tailscale.com => github.com/Darkaxt/tailscale v[^\s]+-[0-9a-f]{12}',data['core_replace']):
        raise PackageError('invalid-core-pin')
    if data['authenticode']!='not-signed':raise PackageError('unsupported-signature-label')
    rows=data['files'];names=set()
    if not isinstance(rows,list) or not 1<=len(rows)<=10000:raise PackageError('package-resource-limit')
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'path','size','sha256'}:raise PackageError('invalid-package-member')
        name=relative_name(row['path']);fold=name.casefold()
        if fold in names or name in METADATA or type(row['size']) is not int or not 0<=row['size']<=2**31 or not isinstance(row['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',row['sha256']):
            raise PackageError('invalid-package-member')
        names.add(fold)
    essentials={'taild.exe','taild.setup.exe','desktop/taild.desktop.exe','desktop/ui/index.html','_internal/python314.dll',
        'desktop/licenses/frontend-gpl-3.0.txt','desktop/licenses/frontend-dependencies.txt','licenses/runtime-license-inventory.json'}
    if not essentials<=names:raise PackageError('incomplete-package')
    return data


def verify(root,public_key=PUBLIC_KEY,installed=False):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    root=Path(root).absolute()
    for parent in (root,*root.parents):
        if parent.exists():ordinary(parent)
    manifest=root/MANIFEST;signature=root/SIGNATURE
    ordinary(manifest);ordinary(signature)
    if manifest.stat().st_size>2*1024*1024 or signature.stat().st_size!=64:raise PackageError('invalid-package-signature')
    raw=manifest.read_bytes()
    try:Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key,validate=True)).verify(signature.read_bytes(),raw)
    except Exception:raise PackageError('invalid-package-signature') from None
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise PackageError('duplicate-manifest-field')
            result[key]=value
        return result
    data=validate(json.loads(raw,object_pairs_hook=unique))
    if inventory(root,installed,{r['path'] for r in data['files']})!=data['files']:raise PackageError('package-content-mismatch')
    if not installed and any((root/name).exists() for name in ('installation.json','installation.pending.json')):
        raise PackageError('unexpected-installed-metadata')
    return data


def newer(candidate,current):
    if candidate['subversion']<=current['subversion']:raise PackageError('replay-or-downgrade')
    if tuple(map(int,candidate['upstream_version'].split('.')))<tuple(map(int,current['upstream_version'].split('.'))):
        raise PackageError('upstream-downgrade')
