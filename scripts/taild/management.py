"""Explicit incident actions. READ browsing; separate Write vault, never retries."""
import hashlib
import json
import re
import secrets
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, build_opener

import controld
import credentials

OPERATIONS=frozenset(('management-read','management-prepare','management-apply','management-cancel'))


class ManagementError(ValueError):
    pass


def write(token, method, route, payload, organization=None):
    """Only called with a route assembled from a validated change below."""
    headers={'Authorization':'Bearer '+controld._header(token),
             'Content-Type':'application/x-www-form-urlencoded','User-Agent':'TailD-management'}
    if organization is not None:headers['X-Force-Org-Id']=controld._header(organization)
    try:
        with build_opener(controld.NoRedirect).open(Request(controld.API_BASE+route,
                data=urlencode(payload,doseq=True).encode(),headers=headers,method=method)) as response:
            raw=response.read(4*1024*1024+1)
            if len(raw)>4*1024*1024:raise ManagementError('management-outcome-unknown')
            result=json.loads(raw)
    except HTTPError as error:
        status=error.code;error.close()
        raise ManagementError('management-denied' if status in (401,403) else
            'management-rate-limited' if status==429 else 'management-write-rejected') from None
    except (URLError,OSError,ValueError):
        # The server could already have committed. Do not replay automatically.
        raise ManagementError('management-outcome-unknown') from None
    if not isinstance(result,dict) or result.get('success') is not True:
        raise ManagementError('management-write-rejected')
    return {}  # Never reflect a provider write response or credential to the renderer.


def records(snapshot, kind):
    resource=snapshot['resources'].get(kind,{})
    if resource.get('state')!='available':raise ManagementError('management-resource-unavailable')
    data=resource.get('data',{}).get(kind)
    if not isinstance(data,list):raise ManagementError('management-resource-unavailable')
    return data


def associated(device, profile):
    return any(isinstance(device.get(key),dict) and device[key].get('PK')==profile
               for key in ('profile','profile2'))


def affected(snapshot):
    resource=snapshot['resources']['endpoints']
    if resource.get('state')!='available':raise ManagementError('management-resource-unavailable')
    return sorted([{'id':d['PK'],'name':d.get('name',d['PK'])}
                   for d in resource['data']['devices'] if associated(d,snapshot['profile'])],key=lambda d:d['id'])


def fingerprint(snapshot):
    value={'profile':snapshot['profile'],'affected':affected(snapshot),
           'policy':{k: snapshot['resources'].get(k,{}).get('data') for k in
                     ('rules','filters','services','options')}}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def option_catalog(snapshot, token, organization=None):
    resource=snapshot['resources'].get('options',{})
    if resource.get('state')!='available':return snapshot
    catalog=controld._safe_data(controld._body('/profiles/options',token,organization),token).get('options')
    if not isinstance(catalog,list) or not all(isinstance(o,dict) and isinstance(o.get('PK'),str) for o in catalog):
        raise ManagementError('management-resource-unavailable')
    configured={r['PK']:r for r in records(snapshot,'options')}
    resource['data']['options']=[{**o,'value':None,'configured':o['PK'] in configured,
                                 **configured.get(o['PK'],{})} for o in catalog]
    return snapshot


def route_change(snapshot, change):
    if not isinstance(change,dict):raise ManagementError('management-invalid-change')
    kind=change.get('kind');profile=controld._identifier(snapshot['profile'])
    path='/profiles/'+profile
    def status():
        if type(change.get('status')) is not int or change['status'] not in (0,1):
            raise ManagementError('management-invalid-change')
        return change['status']
    if kind=='rule':
        if set(change)-{'kind','hostname','do','status','comment','delete'}:
            raise ManagementError('management-invalid-change')
        hostname=change.get('hostname')
        if not isinstance(hostname,str) or len(hostname)>253 or not re.fullmatch(
                r'(?:\*\.)?[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?)*',hostname):
            raise ManagementError('management-invalid-change')
        hostname=hostname.lower()
        existing=next((r for r in records(snapshot,'rules') if r.get('PK')==hostname),None)
        if change.get('delete') is True:
            if existing is None or set(change)!={'kind','hostname','delete'}:
                raise ManagementError('management-invalid-change')
            return 'DELETE',path+'/rules/'+quote(hostname,safe=''),{}
        if type(change.get('do')) is not int or change['do'] not in (0,1):
            raise ManagementError('management-invalid-change')
        comment=change.get('comment','')
        if not isinstance(comment,str) or len(comment)>64 or any(ord(c)<32 for c in comment):
            raise ManagementError('management-invalid-change')
        payload={'hostnames[]':[hostname],'do':change['do'],'status':status(),'comment':comment}
        # Preserve an existing folder rather than silently moving the rule to root.
        if existing and existing.get('group') is not None:payload['group']=existing['group']
        return 'PUT' if existing else 'POST',path+'/rules',payload
    if kind not in ('filter','service','option') or set(change)-{'kind','id','status','do','value'}:
        raise ManagementError('management-invalid-change')
    key=change.get('id')
    if not isinstance(key,str) or not re.fullmatch('[A-Za-z0-9_-]{1,128}',key):
        raise ManagementError('management-invalid-change')
    resource={'filter':'filters','service':'services','option':'options'}[kind]
    candidates=records(snapshot,resource)
    if kind=='filter':
        ids={r.get('PK') for r in candidates}
        ids.update(level.get('name') for r in candidates for level in r.get('levels',[]))
    else:ids={r.get('PK') for r in candidates}
    if key not in ids:raise ManagementError('management-invalid-change')
    payload={'status':status()}
    if kind=='filter':
        if set(change)!={'kind','id','status'}:raise ManagementError('management-invalid-change')
        path+='/filters/filter/'+key
    elif kind=='service':
        if set(change)!={'kind','id','status','do'} or type(change.get('do')) is not int or change['do'] not in (0,1):
            raise ManagementError('management-invalid-change')
        payload['do']=change['do'];path+='/services/'+key
    else:
        if 'do' in change:raise ManagementError('management-invalid-change')
        if 'value' in change:
            if not isinstance(change['value'],str) or len(change['value'])>1024 or any(ord(c)<32 for c in change['value']):
                raise ManagementError('management-invalid-change')
            payload['value']=change['value']
        path+='/options/'+key
    return 'PUT',path,payload


def verified(snapshot, change, expected_group=None):
    """A successful HTTP response alone is not verified policy application."""
    kind=change['kind']
    if kind=='rule':
        row=next((r for r in records(snapshot,'rules') if r.get('PK')==change['hostname'].lower()),None)
        if change.get('delete') is True:return row is None
        return (row is not None and all(row.get('action',{}).get(k)==change[k] for k in ('do','status'))
                and row.get('comment','')==change.get('comment','')
                and (expected_group is None or row.get('group')==expected_group))
    if kind=='filter':
        row=next((r for r in records(snapshot,'filters') if r.get('PK')==change['id'] or
                  any(l.get('name')==change['id'] for l in r.get('levels',[]))),None)
        if row is None:return False
        return row.get('status')==change['status'] and (not change['status'] or
            row.get('action',{}).get('lvl',row.get('PK'))==change['id'])
    rows=records(snapshot,{'service':'services','option':'options'}[kind])
    row=next((r for r in rows if r.get('PK')==change['id']),None)
    if row is None:return False
    if kind=='service':return all(row.get('action',{}).get(k)==change[k] for k in ('do','status'))
    if not change['status'] and row.get('configured') is False:return True
    expected=change.get('value','1') if change['status'] else '0'
    return str(row.get('value'))==expected


class Management:
    def __init__(self):
        self.lock=threading.Lock();self.pending=None

    def _read(self, endpoint, provider):
        token=credentials.CredentialStore().read()
        if not token:raise ManagementError('management-read-credential-required')
        return option_catalog(controld.policy_snapshot(token,endpoint,account_scope=provider['account_scope'],
                                        organization=provider.get('organization')),token,provider.get('organization'))

    def _write_token(self, provider):
        read=credentials.CredentialStore().read()
        token=credentials.CredentialStore(credentials.WRITE_TARGET).read()
        if not read or not token:raise ManagementError('management-write-credential-required')
        org=provider.get('organization')
        account=controld._body('/users',read,org).get('PK')
        if account is None or controld._body('/users',token,org).get('PK')!=account:
            raise ManagementError('management-account-mismatch')
        return token

    def dispatch(self, op, body, provider):
        if not provider:raise ManagementError('explicit-provider-required')
        if not isinstance(body,dict):raise ManagementError('management-invalid-change')
        # One pending preview per owning collector. Serializes policy actions,
        # never SQLite acquisition or unrelated analytics reads.
        with self.lock:
            if op=='management-cancel' and not body:
                self.pending=None;return {'cancelled':True}
            if op=='management-read' and set(body)<= {'endpoint'}:
                self.pending=None
                snapshot=self._read(controld._identifier(body.get('endpoint') or provider['endpoint']),provider)
                snapshot['affected_endpoints']=affected(snapshot)
                return snapshot
            if op=='management-prepare' and set(body)=={'endpoint','change'}:
                self.pending=None
                self._write_token(provider)
                snapshot=self._read(controld._identifier(body['endpoint']),provider)
                method,route,payload=route_change(snapshot,body['change'])
                ticket=secrets.token_urlsafe(32)
                self.pending={'ticket':ticket,'provider':dict(provider),'endpoint':snapshot['endpoint'],
                              'fingerprint':fingerprint(snapshot),'change':body['change'].copy()}
                return {'ticket':ticket,'profile':snapshot['profile'],'affected_endpoints':affected(snapshot),
                        'method':method,'change':body['change'],'shared_profile':len(affected(snapshot))>1}
            if op=='management-apply' and set(body)=={'ticket','confirm'} and body['confirm'] is True:
                pending=self.pending;self.pending=None  # Consume before any network mutation.
                if pending is None or body['ticket']!=pending['ticket'] or provider!=pending['provider']:
                    raise ManagementError('management-conflict')
                token=self._write_token(provider)
                snapshot=self._read(pending['endpoint'],provider)
                if fingerprint(snapshot)!=pending['fingerprint']:raise ManagementError('management-conflict')
                method,route,payload=route_change(snapshot,pending['change'])
                write(token,method,route,payload,provider.get('organization'))
                try:
                    after=self._read(pending['endpoint'],provider)
                    if (after['profile']!=snapshot['profile'] or affected(after)!=affected(snapshot) or
                            not verified(after,pending['change'],payload.get('group'))):
                        raise ManagementError('management-outcome-unknown')
                except (controld.ControlDError,ManagementError,credentials.CredentialError):
                    raise ManagementError('management-outcome-unknown') from None
                after['affected_endpoints']=affected(after)
                return {'state':'applied','snapshot':after,'readback':True}
        raise ManagementError('management-invalid-change')
