"""Windows file-version resources preserving the exact inherited base version."""
import argparse
from pathlib import Path
import re


def write(path,upstream,subversion):
    from PyInstaller.utils.win32.versioninfo import VSVersionInfo,FixedFileInfo,StringFileInfo,StringTable,StringStruct,VarFileInfo,VarStruct
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',upstream) or not 0<subversion<65536:raise ValueError('Invalid Windows fork version')
    numeric=(*map(int,upstream.split('.')),subversion);version=upstream+'+'+str(subversion)
    resource=VSVersionInfo(ffi=FixedFileInfo(filevers=numeric,prodvers=numeric,mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),
        kids=[StringFileInfo([StringTable('040904B0',[StringStruct('CompanyName','Darkaxt'),StringStruct('ProductName','TailD'),
            StringStruct('FileDescription','TailD network analytics - independent community fork'),
            StringStruct('FileVersion',version),StringStruct('ProductVersion',version)])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])
    with path.open('x',encoding='utf-8') as f:f.write(str(resource))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--upstream',required=True);parser.add_argument('--subversion',required=True,type=int)
    args=parser.parse_args();write(args.output,args.upstream,args.subversion)
