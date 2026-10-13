"""Whitelisted private migration evidence; no provider writes or VPN mutation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess

import analytics
import controld
import credentials
import history
import installer
import package_manifest


def cli_read(cli,*arguments):
    return subprocess.check_output([str(cli),*arguments],stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)


def snapshot():
    import win32service
    root=installer.app_directory().parent;cli=root/'tailscale.exe'
    status=json.loads(cli_read(cli,'status','--json'));prefs=json.loads(cli_read(cli,'debug','prefs'))
    public=cli_read(cli,'lock','status').decode()
    key=re.search(r"This node's tailnet-lock key:\s*(tlpub:[0-9a-f]+)",public)
    if (status.get('BackendState')!='Running' or not status.get('HaveNodeKey') or key is None or
        'This node is accessible under Tailnet Lock' not in public):raise ValueError('Authenticated signer baseline unavailable')
    manager=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CONNECT)
    try:service=win32service.OpenService(manager,'Tailscale',win32service.SERVICE_QUERY_CONFIG|win32service.SERVICE_QUERY_STATUS)
    finally:manager.Close()
    try:
        config=win32service.QueryServiceConfig(service);state=win32service.QueryServiceStatusEx(service)
        service_data={'command':config[3],'start_type':config[1],'state':state['CurrentState']}
    finally:service.Close()
    files={}
    for name in ('tailscaled.exe','tailscale.exe','taildns.exe','taildns-ipn.exe','tailscale-ipn.exe','wintun.dll'):
        path=root/name
        if not path.exists():continue
        with path.open('rb') as source:files[name]=hashlib.file_digest(source,'sha256').hexdigest()
    node=status['Self']
    return {'schema':'taild-private-migration-evidence-v1','node_id':node['ID'],
        'addresses':sorted(node['TailscaleIPs']),'dns_name':node['DNSName'],'tailnet_lock_public_key':key[1],
        'context':analytics.capture_context(cli),'service':service_data,'files':files,
        'auto_update':prefs.get('AutoUpdate'),'version':json.loads(cli_read(cli,'version','--json'))}


def capture(output,endpoint):
    output=history.private_directory(output);data=snapshot()
    with (output/'before.json').open('x',encoding='utf-8') as target:json.dump(data,target,indent=2)
    token=credentials.CredentialStore().read()
    if token is None:raise ValueError('Owner READ credential unavailable')
    inventory=controld.inventory(token);account=controld._body('/users',token)
    selected=[d for d in inventory['devices'] if endpoint in (d.get('PK'),d.get('device_id'))]
    if len(selected)!=1 or account.get('org_id'):raise ValueError('Explicit unique personal endpoint required')
    provider={'account_scope':'controld-'+history.digest([account['PK']])[:32],
        'endpoint':selected[0]['PK'],'account_type':'personal','instance':controld.analytics_instance(token)}
    token=None
    with (output/'provider-selection.json').open('x',encoding='utf-8') as target:json.dump(provider,target,indent=2)
    print(json.dumps({'baseline_captured':True,'provider_selection_verified':True,'provider_writes':False,
        'override_configured':data['context']['local_override'],'private_values_printed':False}))


def compare(output):
    before=json.loads((output/'before.json').read_bytes());after=snapshot()
    for key in ('node_id','addresses','dns_name','tailnet_lock_public_key','service','auto_update'):
        if before[key]!=after[key]:raise ValueError('Migration continuity check failed: '+key)
    for key in ('dns_accepted','local_override','resolver_endpoint','resolver_applied','exit_node_id','exit_node_ip',
        'profile_id','portal_mode','magic_dns_enabled','magic_dns_suffix','split_dns_routes','search_domains'):
        if before['context'][key]!=after['context'][key]:raise ValueError('DNS/context setting changed: '+key)
    for name in ('tailscale-ipn.exe','wintun.dll'):
        if before['files'].get(name)!=after['files'].get(name):raise ValueError('Preserved component changed')
    app=installer.app_directory();data=package_manifest.verify(app,installed=True)
    for payload,destination in (('taildnsd.exe','tailscaled.exe'),('tailscale.exe','tailscale.exe'),
        ('taildns.exe','taildns.exe'),('taildns-ipn.exe','taildns-ipn.exe')):
        with (app/'connectivity'/payload).open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
        if after['files'][destination]!=digest:raise ValueError('Installed connectivity does not match the signed package')
    if after['version']['long']!=data['upstream_version']+'-taild.'+str(data['subversion']):
        raise ValueError('Installed fork version mismatch')
    socket.getaddrinfo('example.com',443)
    own={item[4][0] for item in socket.getaddrinfo(after['dns_name'],443)}
    if not set(after['addresses']) & own:raise ValueError('Own MagicDNS address resolution failed')
    with (output/('after-'+str(data['subversion'])+'.json')).open('x',encoding='utf-8') as target:json.dump(after,target,indent=2)
    print(json.dumps({'verified':True,'version':data['version'],'node_addresses_signer_preserved':True,
        'dns_preferences_preserved':True,'public_and_magic_dns':True,'complete_package_verified':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('capture','compare'));parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--endpoint')
    args=parser.parse_args()
    if args.operation=='capture':capture(args.output,args.endpoint)
    else:compare(args.output)
