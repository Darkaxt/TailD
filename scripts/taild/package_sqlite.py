"""One pinned official SQLite DLL for the complete frozen Windows product."""
import argparse,ctypes,hashlib,io,json,os,sqlite3,struct,sys,zipfile
from pathlib import Path
from urllib.request import urlopen

VERSION='3.54.0'
URL='https://www.sqlite.org/2026/sqlite-dll-win-x64-3540000.zip'
ARCHIVE_SHA3='f5fb500c73a3afd89976386bb8e4fdc8b5b65c052e187fb1ada1f5de034cd45b'
DLL_SHA256='5ca6a16bdd2c5a5037b1e3a942d9ac1c66efe2def902b202d44774680a8a4656'

def require_runtime():
    if getattr(sys,'frozen',False) and sqlite3.sqlite_version!=VERSION:
        raise RuntimeError('unsafe-sqlite-runtime')

def unpack(raw):
    if hashlib.sha3_256(raw).hexdigest()!=ARCHIVE_SHA3:raise ValueError('sqlite-archive-digest')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if sorted(archive.namelist())!=['sqlite3.def','sqlite3.dll']:raise ValueError('sqlite-archive-members')
        if archive.getinfo('sqlite3.dll').file_size>8*1024*1024:raise ValueError('sqlite-dll-size')
        dll=archive.read('sqlite3.dll')
    if hashlib.sha256(dll).hexdigest()!=DLL_SHA256:raise ValueError('sqlite-dll-digest')
    offset=struct.unpack_from('<I',dll,0x3c)[0]
    if dll[offset:offset+4]!=b'PE\0\0' or struct.unpack_from('<H',dll,offset+4)[0]!=0x8664:raise ValueError('sqlite-dll-architecture')
    return dll

def stage(package):
    package=Path(package).resolve(strict=True);target=package/'_internal'/'sqlite3.dll'
    if not target.is_file() or target.is_symlink() or target.stat().st_nlink!=1:raise ValueError('sqlite-package-target')
    with urlopen(URL) as response:raw=response.read(4*1024*1024+1)
    if len(raw)>4*1024*1024:raise ValueError('sqlite-archive-size')
    dll=unpack(raw);target.write_bytes(dll)
    if os.name=='nt':
        library=ctypes.CDLL(str(target));library.sqlite3_libversion.restype=ctypes.c_char_p
        if library.sqlite3_libversion().decode()!=VERSION:raise ValueError('sqlite-runtime-version')
    notices=package/'licenses';notices.mkdir(exist_ok=True)
    record={'component':'SQLite','version':VERSION,'architecture':'windows-amd64','url':URL,
        'archive_sha3_256':ARCHIVE_SHA3,'dll_sha256':DLL_SHA256,
        'license':'Public domain','license_url':'https://www.sqlite.org/copyright.html',
        'wal_fix_reference':'https://www.sqlite.org/wal.html#walreset'}
    with (notices/'sqlite-runtime.json').open('x',encoding='utf-8') as output:json.dump(record,output,indent=2)
    print(json.dumps(record))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,required=True)
    stage(parser.parse_args().package)
