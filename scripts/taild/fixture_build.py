"""Credential-free CI build variant, isolated from the production trust identity."""
import argparse
import base64
import hashlib
from pathlib import Path
import shutil

import package_manifest


def create(source,output,public_key):
    if len(base64.b64decode(public_key,validate=True))!=32:raise ValueError('Expected Ed25519 fixture public key')
    output.mkdir(parents=True,exist_ok=False)
    for file in source.glob('*.py'):
        shutil.copyfile(file,output/file.name)
    manifest=output/'package_manifest.py';text=manifest.read_text(encoding='utf-8')
    old="PUBLIC_KEY='"+package_manifest.PUBLIC_KEY+"'"
    if text.count(old)!=1:raise ValueError('Fixture trust substitution is not exact')
    manifest.write_text(text.replace(old,"PUBLIC_KEY='"+public_key+"'"),encoding='utf-8')
    return hashlib.sha256(manifest.read_bytes()).hexdigest()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--public-key',required=True)
    args=parser.parse_args();print(create(args.source,args.output,args.public_key))
