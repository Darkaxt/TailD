"""Dedicated TailD signed installer channel. No token, policy or VPN mutation.

An installer is executable only after the separate pinned-key envelope and its
complete streamed bytes have verified. Interrupted work stays non-executable.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import quote,urlsplit,unquote
import urllib.request

import package_manifest

ENVELOPE='taild-release.json'
SIGNATURE=ENVELOPE+'.sig'
API='https://api.github.com/repos/Darkaxt/TailD/releases/latest'
MAX_INSTALLER=1024**3


class ChannelError(ValueError):pass


def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ChannelError('duplicate-release-field')
        result[key]=value
    return result


def validate(data):
    fields={'schema','product','version','upstream_version','subversion','architecture',
        'source_commit','core_replace','history_schema','package_sha256','authenticode','installer'}
    if not isinstance(data,dict) or set(data)!=fields:raise ChannelError('invalid-release-envelope')
    if data['schema']!='taild-release-v1' or data['product']!='TailD' or data['architecture']!='windows-amd64' or data['history_schema']!=4 or data['authenticode']!='not-signed':
        raise ChannelError('incompatible-release')
    if not isinstance(data['upstream_version'],str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',data['upstream_version']):
        raise ChannelError('invalid-release-version')
    if type(data['subversion']) is not int or not 1<=data['subversion']<=65535 or data['version']!=data['upstream_version']+'+'+str(data['subversion']):
        raise ChannelError('invalid-release-version')
    if not isinstance(data['source_commit'],str) or not re.fullmatch('[0-9a-f]{40}',data['source_commit']):raise ChannelError('invalid-release-source')
    if not isinstance(data['core_replace'],str) or not re.fullmatch(r'replace tailscale.com => github.com/Darkaxt/tailscale v[^\s]+-[0-9a-f]{12}',data['core_replace']):raise ChannelError('invalid-release-core')
    if not isinstance(data['package_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',data['package_sha256']):raise ChannelError('invalid-release-package')
    item=data['installer']
    if (not isinstance(item,dict) or set(item)!={'name','size','sha256'} or
        item['name']!='TailD-'+data['version']+'-windows-amd64-setup.exe' or
        type(item['size']) is not int or not 0<item['size']<=MAX_INSTALLER or
        not isinstance(item['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',item['sha256'])):
        raise ChannelError('invalid-release-installer')
    return data


def verify(raw,signature,highest_subversion,current_upstream,public_key=package_manifest.PUBLIC_KEY):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if len(raw)>65536 or len(signature)!=64:raise ChannelError('invalid-release-signature')
    try:Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key,validate=True)).verify(signature,raw)
    except Exception:raise ChannelError('invalid-release-signature') from None
    try:data=validate(json.loads(raw,object_pairs_hook=unique))
    except (TypeError,json.JSONDecodeError):raise ChannelError('invalid-release-envelope') from None
    if (data['subversion']<=highest_subversion or
        tuple(map(int,data['upstream_version'].split('.')))<tuple(map(int,current_upstream.split('.')))):
        raise ChannelError('release-replay-or-downgrade')
    return data


def assets(metadata,data=None):
    if not isinstance(metadata,dict) or metadata.get('draft') is not False or metadata.get('prerelease') is not False:
        raise ChannelError('not-a-normal-release')
    tag=metadata.get('tag_name')
    if not isinstance(tag,str) or not re.fullmatch(r'windows-v[0-9]+\.[0-9]+\.[0-9]+\+[1-9][0-9]*',tag):raise ChannelError('invalid-release-tag')
    if data is not None and tag!='windows-v'+data['version']:raise ChannelError('release-tag-mismatch')
    rows=metadata.get('assets')
    if not isinstance(rows,list) or len(rows)>32:raise ChannelError('invalid-release-assets')
    result={}
    for row in rows:
        name=row.get('name') if isinstance(row,dict) else None
        url=row.get('browser_download_url') if isinstance(row,dict) else None
        if not isinstance(name,str) or name in result or not isinstance(url,str):raise ChannelError('invalid-release-assets')
        expected='https://github.com/Darkaxt/TailD/releases/download/'+quote(tag,safe='')+'/'+quote(name,safe='')
        if unquote(url)!=unquote(expected) or urlsplit(url).query or urlsplit(url).fragment:
            raise ChannelError('untrusted-release-url')
        result[name]=url
    if not {ENVELOPE,SIGNATURE}<=result.keys() or data is not None and data['installer']['name'] not in result:
        raise ChannelError('missing-release-assets')
    return result


def trusted_transport(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443):raise ChannelError('untrusted-transport')
    # GitHub's public release CDN is a distinct protocol boundary. Neither
    # credentials nor cookies are sent, and no arbitrary redirect is accepted.
    if parsed.hostname not in ('api.github.com','github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'):
        raise ChannelError('untrusted-transport')


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,response,code,message,headers,url):
        trusted_transport(url)
        return super().redirect_request(request,response,code,message,headers,url)


def open_url(url):
    trusted_transport(url)
    request=urllib.request.Request(url,headers={'User-Agent':'TailD-Updater','Accept':'application/vnd.github+json'})
    # This is only the HTTP transport boundary's inactivity limit, not a deadline
    # on a build/install, recovery mechanism or classification of app lifecycle.
    response=urllib.request.build_opener(Redirect()).open(request,timeout=60)
    if response.status!=200:response.close();raise ChannelError('release-http-status')
    return response


def bounded(url,limit):
    with open_url(url) as response:
        raw=response.read(limit+1)
    if len(raw)>limit:raise ChannelError('release-resource-limit')
    return raw


def stage(stream,directory,data):
    validate(data);directory=Path(directory)
    for parent in (directory,*directory.parents):
        if parent.exists():package_manifest.ordinary(parent)
    item=data['installer'];final=directory/item['name'];partial=final.with_suffix('.exe.partial')
    package_manifest.ordinary(final);package_manifest.ordinary(partial)
    if final.exists():raise ChannelError('release-already-staged')
    digest=hashlib.sha256();size=0
    # A specifically named partial download is never run. An explicit subsequent
    # invocation can overwrite it; no retry loop or stale-lock stealing is used.
    with partial.open('wb') as output:
        while block:=stream.read(min(1024*1024,item['size']-size+1)):
            size+=len(block)
            if size>item['size']:raise ChannelError('installer-size-mismatch')
            digest.update(block);output.write(block)
        output.flush();os.fsync(output.fileno())
    if size!=item['size'] or digest.hexdigest()!=item['sha256']:raise ChannelError('installer-content-mismatch')
    # Windows rename refuses an existing destination, preserving another writer.
    partial.rename(final)
    return final


def prepare(directory,highest_subversion,current_upstream):
    metadata=json.loads(bounded(API,1024*1024),object_pairs_hook=unique)
    locations=assets(metadata)
    raw=bounded(locations[ENVELOPE],65536);sig=bounded(locations[SIGNATURE],64)
    data=verify(raw,sig,highest_subversion,current_upstream)
    locations=assets(metadata,data)
    Path(directory).mkdir(parents=True,exist_ok=False)
    with open_url(locations[data['installer']['name']]) as stream:
        executable=stage(stream,directory,data)
    return executable,data
