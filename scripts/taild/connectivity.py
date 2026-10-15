"""Fixed owning-user Tailscale controls, using the inherited CLI/LocalAPI.

No shell, new daemon, credential export, automatic mutation retry or elevation.
Only the whitelisted view below crosses the renderer boundary.
"""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import core_manifest

OPERATIONS=('connectivity-read','connectivity-edit','connectivity-reset','connectivity-about')
PREFERENCES=(
    ('allow-incoming','Allow incoming connections','ShieldsUp','EnableIncomingConnections'),
    ('use-dns','Use TailD DNS settings','CorpDNS','EnableTailscaleDNS'),
    ('use-subnets','Use Tailscale subnets','RouteAll','EnableTailscaleSubnets'),
    ('auto-update','Automatically install TailD updates','AutoUpdate','ApplyUpdates'),
    ('unattended','Run unattended','ForceDaemon','EnableServerMode'))


def instance_name(instance):
    return 'settings-'+hashlib.sha256(instance.encode('ascii')).hexdigest()[:32]


class ConnectivityError(Exception):
    pass


def valid_resolver(value):
    if not isinstance(value,str) or len(value)>2048 or any(c.isspace() or ord(c)<32 for c in value):return False
    try:
        url=urlsplit(value)
        if (url.scheme!='https' or not url.hostname or not url.path or url.username or url.password
            or '?' in value or '#' in value or url.port not in (None,443) or url.netloc.endswith(':')):return False
        try:ipaddress.ip_address(url.hostname);return False
        except ValueError:pass
        labels=url.hostname.removesuffix('.').split('.')
        return len(labels)>1 and all(label and len(label)<=63 and label[0].isalnum() and label[-1].isalnum()
            and all(c.isascii() and (c.isalnum() or c=='-') for c in label) for label in labels)
    except ValueError:return False


class Connectivity:
    def __init__(self,cli,*,call=None):
        self.cli=Path(cli).absolute() if cli else None
        self.call=call or self._call
        self.lock=threading.Lock()

    def _call(self,method,path,body=None):
        if self.cli is None:raise ConnectivityError('connectivity-unavailable')
        args=[str(self.cli),'version','--json'] if path=='version' and method=='GET' else [
            str(self.cli),'debug','localapi',method,'/localapi/v0/'+path,*(['-'] if body is not None else [])]
        try:
            process=subprocess.run(args,input=json.dumps(body).encode() if body is not None else None,
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,check=False)
            if process.returncode or len(process.stdout)>2*1024*1024:raise ConnectivityError('connectivity-unavailable')
            result=json.loads(process.stdout) if process.stdout.strip() else {}
            if not isinstance(result,dict):raise ValueError()
            return result
        except (OSError,ValueError):raise ConnectivityError('connectivity-unavailable') from None

    @staticmethod
    def _policy(policy,key):
        item=policy.get('Settings',{}).get(key,{})
        if not isinstance(item,dict) or item.get('Error'):raise ConnectivityError('connectivity-unavailable')
        return item.get('Value')

    def read(self):
        try:return self._snapshot()
        except (ValueError,KeyError,TypeError,AttributeError):
            raise ConnectivityError('connectivity-unavailable') from None

    def _read_all(self):
        paths=('status','prefs','profiles/current','local-dns','policy/')
        # These fixed GETs are independent. Join every owned call; no retry,
        # timeout or discarded process substitutes for actual completion.
        with ThreadPoolExecutor(max_workers=len(paths),thread_name_prefix='TailD settings read') as pool:
            calls=[pool.submit(self.call,'GET',path) for path in paths]
            return [call.result() for call in calls]

    def _snapshot(self):
        status,prefs,profile,resolver,policy=self._read_all()
        get=lambda key:self._policy(policy,key)
        visible=lambda key:str(get(key)).lower()!='hide'
        editable=lambda key:str(get(key)).lower() not in ('always','never')
        profile_id=profile.get('ID','')
        self_info=status.get('Self') or {}
        preferences=[]
        for action,label,field,key in PREFERENCES:
            value=not bool(prefs.get(field)) if field=='ShieldsUp' else (
                prefs.get('AutoUpdate',{}).get('Apply') is True if field=='AutoUpdate' else bool(prefs.get(field)))
            show=visible('PreferencesMenuVisibility') and (action!='auto-update' or visible('UpdateMenuVisibility'))
            preferences.append({'id':action,'label':label,'value':value,'visible':show,
                'editable':bool(profile_id) and show and editable(key)})
        resolver_fields={'ProfileID':str,'Configured':bool,'Endpoint':str,'Applied':bool,'CaptivePortal':bool,'Reason':str}
        if any(type(resolver.get(key)) is not kind for key,kind in resolver_fields.items()):
            raise ConnectivityError('connectivity-unavailable')
        if resolver['ProfileID']!=profile_id:raise ConnectivityError('connectivity-conflict')
        safe_resolver={key:resolver[key] for key in resolver_fields}
        peers=[{'id':p.get('ID'),'name':p.get('HostName') or p.get('DNSName'),
            'addresses':p.get('TailscaleIPs') or [],'online':bool(p.get('Online')),'exit':bool(p.get('ExitNodeOption'))}
            for p in (status.get('Peer') or {}).values()]
        safe_prefs={key:prefs.get(key) for key in ('WantRunning','ExitNodeID','ExitNodeAllowLANAccess')}
        safe_prefs['AdvertiseRoutes']=prefs.get('AdvertiseRoutes') or []
        safe_prefs['RunExitNode']=all(route in safe_prefs['AdvertiseRoutes'] for route in ('0.0.0.0/0','::/0'))
        view={'profile':profile_id,'account':profile.get('Name') or '',
            'state':status.get('BackendState') or 'Unavailable','device':self_info.get('HostName') or '',
            'addresses':self_info.get('TailscaleIPs') or [],'daemon_version':status.get('Version') or '',
            'preferences':preferences,'prefs':safe_prefs,'resolver':safe_resolver,
            'peers':sorted(peers,key=lambda p:p['name'] or ''),
            'show_peers':visible('NetworkDevicesVisibility'),'show_exit':visible('ExitNodeMenuVisibility'),
            'show_run_exit':visible('RunExitNodeVisibility'),'show_reset':visible('ResetToDefaultsVisibility'),
            'can_disconnect':bool(profile_id) and get('AlwaysOn.Enabled') is not True,
            'can_exit':bool(profile_id) and visible('ExitNodeMenuVisibility') and not get('ExitNodeID'),
            'can_exit_lan':bool(profile_id) and editable('ExitNodeAllowLANAccess'),
            'can_run_exit':bool(profile_id) and visible('RunExitNodeVisibility') and editable('EnableRunExitNode'),
            'can_resolver':bool(profile_id) and editable('EnableTailscaleDNS'),
            'can_reset':bool(profile_id) and visible('ResetToDefaultsVisibility') and all(p['editable'] for p in preferences)}
        # Only editable state is hashed: peer traffic/health updates must not
        # invalidate an unrelated preference click. No private prefs are hashed.
        revision={key:view[key] for key in ('profile','preferences','prefs','resolver','can_disconnect','can_exit','can_exit_lan','can_run_exit','can_resolver','can_reset')}
        revision['resolver']={key:safe_resolver[key] for key in ('ProfileID','Configured','Endpoint')}
        view['revision']=hashlib.sha256(json.dumps(revision,sort_keys=True).encode()).hexdigest()
        return view

    def about(self):
        try:version=self.call('GET','version').get('long') or 'Unavailable'
        except ConnectivityError:version='Unavailable'
        return {'product':'TailD','version':version.replace('-taild.','+'),'cli_version':version,
            'core':core_manifest.CORE,'independent_fork':True,'license':'GPL-3.0-only desktop / inherited BSD-3-Clause core',
            'project':'https://github.com/Darkaxt/TailD','releases':'https://github.com/Darkaxt/TailD/releases'}

    def dispatch(self,op,body):
        if op not in OPERATIONS or not isinstance(body,dict):raise ConnectivityError('invalid-command')
        with self.lock:
            if op in ('connectivity-read','connectivity-about'):
                if body:raise ConnectivityError('invalid-command')
                return self.read() if op=='connectivity-read' else self.about()
            allowed={'revision','confirm'} if op=='connectivity-reset' else {'revision','preference','value','confirm'}
            if set(body)-allowed or not isinstance(body.get('revision'),str):raise ConnectivityError('invalid-command')
            if 'confirm' in body and type(body['confirm']) is not bool:raise ConnectivityError('invalid-command')
            current=self.read()
            if body['revision']!=current['revision']:raise ConnectivityError('connectivity-conflict')
            if not current['profile']:raise ConnectivityError('connectivity-denied')
            if op=='connectivity-reset':
                if body.get('confirm') is not True:raise ConnectivityError('connectivity-confirm-required')
                if not current['can_reset'] or not current['can_exit'] or not current['can_exit_lan'] or not current['can_resolver']:
                    raise ConnectivityError('connectivity-denied')
                patch={'RouteAll':True,'CorpDNS':True,'ShieldsUp':False,'ForceDaemon':False,
                    'ExitNodeID':'','ExitNodeAllowLANAccess':False,'LocalDNSOverride':False,
                    'AutoUpdate':{'Check':True,'Apply':False}}
                patch.update({key+'Set':True for key in tuple(patch) if key!='AutoUpdate'})
                patch['AutoUpdateSet']={'CheckSet':True,'ApplySet':True}
                route='prefs';expected=None
            else:
                pref,value=body.get('preference'),body.get('value');route='prefs';expected=value
                definition=next((p for p in PREFERENCES if p[0]==pref),None)
                if definition:
                    if type(value) is not bool:raise ConnectivityError('invalid-command')
                    if not next(p for p in current['preferences'] if p['id']==pref)['editable']:raise ConnectivityError('connectivity-denied')
                    field=definition[2]
                    patch={field: not value if field=='ShieldsUp' else value,field+'Set':True}
                    if field=='AutoUpdate':patch={field:{'Check':value,'Apply':value},field+'Set':{'CheckSet':True,'ApplySet':True}}
                elif pref=='connected':
                    if type(value) is not bool:raise ConnectivityError('invalid-command')
                    if not value and body.get('confirm') is not True:raise ConnectivityError('connectivity-confirm-required')
                    if not current['can_disconnect']:raise ConnectivityError('connectivity-denied')
                    patch={'WantRunning':value,'WantRunningSet':True}
                elif pref=='exit-node':
                    if not isinstance(value,str) or value not in ['']+[p['id'] for p in current['peers'] if p['exit']]:raise ConnectivityError('invalid-command')
                    if not current['can_exit']:raise ConnectivityError('connectivity-denied')
                    patch={'ExitNodeID':value,'ExitNodeIDSet':True}
                elif pref=='exit-node-lan':
                    if type(value) is not bool:raise ConnectivityError('invalid-command')
                    if not current['can_exit'] or not current['can_exit_lan']:raise ConnectivityError('connectivity-denied')
                    patch={'ExitNodeAllowLANAccess':value,'ExitNodeAllowLANAccessSet':True}
                elif pref=='run-exit-node':
                    if type(value) is not bool:raise ConnectivityError('invalid-command')
                    if not current['can_run_exit']:raise ConnectivityError('connectivity-denied')
                    routes=[route for route in current['prefs']['AdvertiseRoutes'] if route not in ('0.0.0.0/0','::/0')]
                    if value:routes+=['0.0.0.0/0','::/0']
                    patch={'AdvertiseRoutes':routes,'AdvertiseRoutesSet':True}
                elif pref in ('resolver','resolver-enabled'):
                    if not current['can_resolver']:raise ConnectivityError('connectivity-denied')
                    enabled=True;endpoint=value
                    if pref=='resolver-enabled':
                        if type(value) is not bool:raise ConnectivityError('invalid-command')
                        enabled=value;endpoint=current['resolver'].get('Endpoint') if enabled else ''
                    if enabled and not valid_resolver(endpoint):raise ConnectivityError('connectivity-invalid-resolver')
                    route='local-dns';patch={'ProfileID':current['profile'],'Enabled':enabled,'Endpoint':endpoint}
                else:raise ConnectivityError('invalid-command')
            try:
                self.call('PATCH',route,patch)
                updated=self.read()
            except (ConnectivityError,OSError,ValueError):
                raise ConnectivityError('connectivity-outcome-unknown') from None
            if updated['profile']!=current['profile']:raise ConnectivityError('connectivity-outcome-unknown')
            if expected is not None:
                if definition:actual=next(p for p in updated['preferences'] if p['id']==pref)['value']
                elif pref=='resolver':actual=updated['resolver'].get('Endpoint')
                elif pref=='resolver-enabled':actual=updated['resolver'].get('Configured')
                else:actual=updated['prefs'].get({'connected':'WantRunning','exit-node':'ExitNodeID','exit-node-lan':'ExitNodeAllowLANAccess','run-exit-node':'RunExitNode'}[pref])
                if actual!=expected:raise ConnectivityError('connectivity-outcome-unknown')
            else:
                # The reset is one masked daemon edit, not several CLI mutations.
                raw=self.call('GET','prefs')
                if any(raw.get(k)!=v for k,v in patch.items() if not k.endswith('Set')):
                    raise ConnectivityError('connectivity-outcome-unknown')
            return updated
