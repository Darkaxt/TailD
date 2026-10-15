"""Collect actual bundled runtime licenses, not developer machine inventory."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import ssl
import sys
import urllib.request
import package_sqlite

RUNTIME_DISTRIBUTIONS=('pywin32','pyinstaller','cryptography','cffi','pycparser',
    'aiohttp','aiohappyeyeballs','aiosignal','attrs','frozenlist','multidict','propcache','yarl','idna')


def collect(output,nuget):
    output=Path(output);records=[]
    sqlite_notice=output/'sqlite-runtime.json'
    sqlite_record=json.loads(sqlite_notice.read_bytes())
    if sqlite_record['version']!=package_sqlite.VERSION or sqlite_record['dll_sha256']!=package_sqlite.DLL_SHA256:
        raise ValueError('SQLite notice does not match the pinned bundled runtime')
    records.append({'component':'SQLite','version':sqlite_record['version'],'notice':sqlite_notice.name,
        'sha256':hashlib.sha256(sqlite_notice.read_bytes()).hexdigest()})
    def copy(source,name,component,version):
        source=Path(source).resolve(strict=True);target=output/name
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise ValueError('Notice output already exists')
        shutil.copyfile(source,target)
        records.append({'component':component,'version':version,'notice':name,
            'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    copy(Path(sys.base_prefix)/'LICENSE.txt','python/LICENSE.txt','CPython',sys.version.split()[0])
    if not ssl.OPENSSL_VERSION.startswith('OpenSSL 3.5.7 '):raise ValueError('Review the new CPython TLS runtime license pin')
    with urllib.request.urlopen('https://raw.githubusercontent.com/openssl/openssl/refs/tags/openssl-3.5.7/LICENSE.txt') as response:
        license_text=response.read(65536)
    digest=hashlib.sha256(license_text).hexdigest()
    if digest!='7d5450cb2d142651b8afa315b5f238efc805dad827d91ba367d8516bc9d49e7a':raise ValueError('OpenSSL license input changed')
    target=output/'openssl-3.5.7-LICENSE.txt'
    with target.open('xb') as f:f.write(license_text)
    records.append({'component':'CPython TLS OpenSSL','version':ssl.OPENSSL_VERSION,'notice':target.name,'sha256':digest})
    for name in RUNTIME_DISTRIBUTIONS:
        package=importlib.metadata.distribution(name)
        files=[p for p in package.files if '.dist-info/licenses/' in str(p).replace('\\','/')]
        if not files:raise ValueError('Missing distribution notices: '+name)
        for source in files:
            path=str(source).replace('\\','/').split('.dist-info/licenses/',1)[1]
            copy(package.locate_file(source),name+'/'+path,name,package.version)
    for component,version in (('microsoft.web.webview2','1.0.4258.31'),
        ('microsoft.netcore.app.runtime.win-x64','10.0.12'),
        ('microsoft.windowsdesktop.app.runtime.win-x64','10.0.12')):
        directory=Path(nuget)/component/version
        files=[p for p in directory.iterdir() if p.is_file() and ('LICENSE' in p.name.upper() or 'NOTICE' in p.name.upper())]
        if not files:raise ValueError('Missing runtime notices: '+component)
        for source in files:copy(source,component+'/'+source.name,component,version)
    with (output/'runtime-license-inventory.json').open('x',encoding='utf-8') as f:
        json.dump({'schema':'taild-runtime-notices-v1','components':records},f,indent=2)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--nuget',required=True,type=Path)
    args=parser.parse_args();collect(args.output,args.nuget)
