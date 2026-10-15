"""Read-only Control D capability slice. No policy writes or background collection."""

import argparse
import calendar
import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from email.utils import parsedate_to_datetime

API_BASE = 'https://api.controld.com'
REPO_ROOT = Path(__file__).resolve().parents[2]


class ControlDError(RuntimeError):
    def __init__(self, message, *, status=None, retry_after=None, state='incompatible'):
        super().__init__(message)
        self.status, self.retry_after, self.state = status, retry_after, state


def _retry_after(value):
    if isinstance(value, str) and re.fullmatch('[0-9]{1,10}', value):
        return int(value)
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def _error_state(status):
    if status in (401,403): return 'denied'
    if status == 429: return 'rate-limited'
    if status in (404,405): return 'unavailable'
    if 500 <= status < 600: return 'stale'
    return 'incompatible'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        # Never forward a bearer token to a redirect destination, even same-host.
        return None


def utc_now():
    return datetime.now(timezone.utc)


def _header(value):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ControlDError('Invalid credential or organization header')
    return value.strip()


def _read(url, token, organization=None):
    headers = {'Authorization': 'Bearer ' + _header(token), 'User-Agent': 'TailD-readonly-development'}
    if organization is not None:
        headers['X-Force-Org-Id'] = _header(organization)
    try:
        return build_opener(NoRedirect).open(Request(url, headers=headers, method='GET'))
    except HTTPError as error:
        status = error.code
        retry = _retry_after(error.headers.get('Retry-After'))
        error.close()
        raise ControlDError(f'Control D read rejected (HTTP {status})', status=status,
                            retry_after=retry, state=_error_state(status)) from None
    except (URLError, OSError):
        raise ControlDError('Control D network read failed', state='stale') from None


def _body(path, token, organization=None):
    return _json_body(API_BASE + path,token,organization)


def _json_body(url, token, organization=None):
    with _read(url, token, organization) as response:
        try:
            raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise ControlDError('Control D JSON response exceeds the resource budget', state='incomplete')
            envelope = json.loads(raw)
        except OSError:
            raise ControlDError('Control D network read failed',state='stale') from None
        except ValueError:
            raise ControlDError('Invalid Control D JSON response') from None
    if not isinstance(envelope, dict) or envelope.get('success') is not True:
        code = (envelope.get('error') or {}).get('code') if isinstance(envelope,dict) and isinstance(envelope.get('error'),dict) else None
        if isinstance(code,(int,str)) and re.fullmatch('[0-9]{3,12}',str(code)):
            status = int(str(code)[:3])
            raise ControlDError('Control D returned an unsuccessful read', status=status, state=_error_state(status))
        raise ControlDError('Control D returned an unsuccessful read')
    if not isinstance(envelope.get('body'), dict):
        raise ControlDError('Invalid Control D JSON envelope')
    return envelope['body']


def inventory(token, organization=None):
    result = {'source': 'controld-api'}
    for controller in ('devices', 'profiles'):
        records = _body('/' + controller, token, organization).get(controller)
        if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
            raise ControlDError('Invalid Control D inventory envelope')
        result[controller] = records
    return result


VENDOR_SOURCE = 'https://controld.com/_next/static/chunks/pages/_app-9271d14cae999d91.js'
SERVICE_SOURCE = 'https://controld.com/_next/static/chunks/3622-b5490dd45f8ebe30.js'
POLICY_READS = (
    ('filters', 'filters', 'filters', VENDOR_SOURCE, list),
    ('external_filters', 'filters/external', 'filters', VENDOR_SOURCE, list),
    ('services', 'services', 'services', SERVICE_SOURCE, list),
    ('rules', 'rules/all', 'rules', VENDOR_SOURCE, list),
    ('folders', 'groups', 'groups', VENDOR_SOURCE, list),
    ('options', 'options', 'options', VENDOR_SOURCE, (list,dict)),
    ('restrictions', 'restrictions', 'restrictions', 'https://docs.controld.com/reference/get_profiles-profile-id-restrictions', list),
    ('default_rule', 'default', 'default', VENDOR_SOURCE, (dict,list)),
)


def _identifier(value):
    if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9_-]{1,128}',value):
        raise ControlDError('Expected an explicit provider object identifier')
    return value


def _safe_data(value, token, depth=0):
    if depth > 24:
        raise ControlDError('Provider data exceeds the nesting budget')
    if isinstance(value,dict):
        if any(token in k for k in value):
            raise ControlDError('Credential-bearing provider field refused')
        return {k:_safe_data(v,token,depth+1) for k,v in value.items()
                if k.lower().replace('_','').replace('-','') not in
                ('token','apitoken','apikey','authorization','password','secret','credentials','credential')}
    if isinstance(value,list):
        if len(value)>10000: raise ControlDError('Provider collection exceeds the resource budget',state='incomplete')
        return [_safe_data(v,token,depth+1) for v in value]
    if isinstance(value,str) and token in value:
        raise ControlDError('Credential-bearing provider data refused')
    return value


def _resource(path, controller, expected, token, organization, documentation, *, instance=None):
    result={'method':'GET','route':path,'documentation':documentation,'permission':'Read',
            'validated_at_utc':utc_now().isoformat(),'pagination':'not-documented',
            'response_shape':'body.'+controller,
            'scope':'explicit-authenticated-account'+('/organization' if organization else ''),
            'retention':'provider-controlled/not-guaranteed','unknown_fields':'preserved-except-credentials'}
    try:
        body=_safe_data((_body(path,token,organization) if instance is None else
            _json_body('https://'+_instance(instance)+'.analytics.controld.com'+path,token,organization)),token)
        records=body.get(controller)
        if not isinstance(records,expected):
            raise ControlDError('Invalid Control D resource envelope')
        if isinstance(records,list):
            entry_type=str if controller=='restrictions' and path!='/profiles/restrictions' else dict
            if any(not isinstance(r,entry_type) for r in records):
                raise ControlDError('Invalid Control D resource entry')
        paged=any(body.get(k) not in (None,False,0,'',[]) for k in
                  ('next','next_cursor','nextCursor','has_more','hasMore','truncated'))
        result.update(state='incomplete' if paged else 'available',data=body,
                      completeness='unconsumed-provider-page' if paged else 'returned-response-only')
    except ControlDError as error:
        result.update(state=error.state,status=error.status,retry_after=error.retry_after,
                      error=str(error),completeness='not-complete')
    return result


def policy_snapshot(token, endpoint, *, account_scope, organization=None):
    endpoint=_identifier(endpoint)
    account_scope=_identifier(account_scope)
    token=_header(token)
    resources={}
    for name,path,controller,doc in (
        ('account','/users','__account__','https://docs.controld.com/reference/authentication'),
        ('endpoints','/devices?last_activity=1','devices','https://docs.controld.com/reference/get_devices'),
        ('profiles','/profiles','profiles','https://docs.controld.com/reference/get_profiles')):
        if name=='account':
            account=_body(path,token,organization)
            # No email, billing state, token lists or full account body in snapshots.
            region=(account.get('org') or {}).get('stats_endpoint') if isinstance(account.get('org'),dict) else account.get('stats_endpoint')
            resources[name]={'state':'available','method':'GET','route':path,'documentation':doc,
                             'permission':'Read','validated_at_utc':utc_now().isoformat(),
                             'data':{'analytics_instance':_instance(region) if region else None,
                                     'organization_selected':organization is not None}}
        else:
            resources[name]=_resource(path,controller,list,token,organization,doc)
            if resources[name]['state']!='available':
                raise ControlDError('Endpoint/profile inventory unavailable; no policy reads performed',
                                    state=resources[name]['state'],status=resources[name].get('status'),
                                    retry_after=resources[name].get('retry_after'))
    devices=resources['endpoints']['data']['devices']
    selected=[d for d in devices if isinstance(d,dict) and d.get('PK')==endpoint]
    if len(selected)!=1 or not isinstance(selected[0].get('profile'),dict):
        raise ControlDError('Selected endpoint has no unique readable profile association')
    profile=_identifier(selected[0]['profile'].get('PK'))
    if not any(isinstance(p,dict) and p.get('PK')==profile for p in resources['profiles']['data']['profiles']):
        raise ControlDError('Endpoint profile is not in the selected account inventory')
    clients=selected[0].get('clients')
    valid_clients=isinstance(clients,list) and all(isinstance(client,dict) for client in clients)
    resources['clients']={'state':'available' if valid_clients else 'incompatible' if isinstance(clients,list) else 'unavailable',
        'method':'GET','route':'/devices?last_activity=1','documentation':'https://docs.controld.com/reference/get_devices',
        'permission':'Read','validated_at_utc':utc_now().isoformat(),
        'data':{'clients':clients} if valid_clients else None,
        'completeness':'returned-response-only' if valid_clients else 'invalid-client-schema' if isinstance(clients,list) else 'field-not-returned'}
    if not isinstance(clients,list):
        region=resources['account']['data']['analytics_instance']
        if region:
            clients=_resource('/v2/client?'+urlencode({'endpointId':endpoint}),'items',dict,
                              token,organization,VENDOR_SOURCE,instance=region)
            if clients.get('data'):
                identity=_identifier(selected[0].get('device_id',endpoint))
                items=clients['data']['items']
                item=items.get(identity)
                if item is not None and (not isinstance(item,dict) or
                    not isinstance(item.get('clients',{}),dict) or
                    any(not isinstance(v,dict) for v in item.get('clients',{}).values())):
                    clients.update(state='incompatible',data=None,completeness='invalid-client-schema')
                else:
                    clients['data']['items']={identity:item} if item is not None else {}
            resources['clients']=clients
    resources['restriction_catalog']=_resource('/profiles/restrictions','restrictions',list,token,
        organization,'https://docs.controld.com/reference/get_profiles-restrictions')
    for name,suffix,controller,documentation,expected in POLICY_READS:
        resources[name]=_resource(f'/profiles/{profile}/{suffix}',controller,expected,token,organization,documentation)
    for resource in resources.values():
        resource.setdefault('scope',account_scope)
        resource.setdefault('pagination','not-documented')
        resource.setdefault('response_shape','whitelisted-provider-body')
        resource.setdefault('retention','provider-controlled/not-guaranteed')
        resource['rate_limit']='no-retry; provider Retry-After metadata on HTTP 429'
    return {'source':'controld-api-readonly','account_scope':account_scope,'endpoint':endpoint,
            'profile':profile,'captured_at_utc':utc_now().isoformat(),'consistency':'separate-api-reads',
            'historical_rule_causality':'not-established','resources':resources}


def _instance(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', value):
        raise ControlDError('Expected a single Control D analytics instance label')
    return value


def analytics_instance(token, organization=None):
    account = _body('/users', token, organization)
    org = account.get('org')
    region = org.get('stats_endpoint') if isinstance(org, dict) else account.get('stats_endpoint')
    return _instance(region)


def _utc(value):
    try:
        if 'T' not in value:
            raise ValueError()
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError()
        return parsed
    except (ValueError, TypeError):
        raise ControlDError('Expected an RFC 3339 UTC timestamp') from None


def activity(token, account_type, instance, start, end=None, endpoint=None,
             organization=None, limit=1):
    if account_type not in ('personal', 'organization'):
        raise ControlDError('Expected personal or organization account type')
    instance = _instance(instance) if instance is not None else analytics_instance(token, organization)
    if limit < 1:
        raise ControlDError('Decision limit must be positive')
    since = _utc(start)
    now = utc_now()
    last_month = now.month - 1 or 12
    last_year = now.year - (now.month == 1)
    earliest = now.replace(year=last_year, month=last_month,
                           day=min(now.day, calendar.monthrange(last_year, last_month)[1]))
    if since < earliest or since > now:
        raise ControlDError('Control D CSV start must be within the past calendar month')
    query = {'startTime': start}
    if end is not None:
        until = _utc(end)
        if until < since or until > now:
            raise ControlDError('Control D CSV end must follow start and not be in the future')
        query['endTime'] = end
    if endpoint is not None:
        query['endpointId'] = endpoint
    url = 'https://' + instance + '.analytics.controld.com/v2/activity-log/csv?' + urlencode(query)
    result = []
    with _read(url, token, organization) as response:
        try:
            reader = csv.DictReader(io.TextIOWrapper(response, encoding='utf-8-sig', newline=''))
            required = {'timestamp', 'endpointId', 'question', 'action'}
            columns=reader.fieldnames or []
            if len(columns)!=len(set(columns)) or not required.issubset(columns):
                raise ControlDError('Invalid Control D decision CSV columns')
            for row in reader:
                if None in row or any(row[column] is None for column in required):
                    raise ControlDError('Invalid Control D decision CSV row')
                _utc(row['timestamp'])
                result.append({'source': 'controld-activity-csv', 'raw': row})
                if len(result) == limit:
                    break
        except (csv.Error, UnicodeError, OSError):
            raise ControlDError('Invalid Control D decision CSV stream') from None
    return result


def export_private(path, data):
    output = Path(path).absolute()
    if output.is_relative_to(REPO_ROOT):
        raise ControlDError('Private exports must be outside the repository')
    try:
        if any(parent.is_symlink() or getattr(parent,'is_junction',lambda:False)() for parent in (output,*output.parents)):
            raise OSError('Linked export destination')
        if os.name=='nt':
            import msvcrt,ntsecuritycon,pywintypes,win32api,win32con,win32file,win32security
            token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32con.TOKEN_QUERY)
            try:sid=win32security.GetTokenInformation(token,win32security.TokenUser)[0]
            finally:token.Close()
            acl=win32security.ACL()
            for principal in (sid,win32security.ConvertStringSidToSid('S-1-5-18'),win32security.ConvertStringSidToSid('S-1-5-32-544')):
                acl.AddAccessAllowedAce(win32security.ACL_REVISION,ntsecuritycon.FILE_ALL_ACCESS,principal)
            security=win32security.SECURITY_DESCRIPTOR();security.SetSecurityDescriptorOwner(sid,False)
            security.SetSecurityDescriptorDacl(True,acl,False)
            security.SetSecurityDescriptorControl(win32security.SE_DACL_PROTECTED,win32security.SE_DACL_PROTECTED)
            attributes=pywintypes.SECURITY_ATTRIBUTES();attributes.SECURITY_DESCRIPTOR=security
            try:handle=win32file.CreateFile(str(output),win32con.GENERIC_WRITE,0,attributes,win32con.CREATE_NEW,win32con.FILE_ATTRIBUTE_NORMAL,None)
            except pywintypes.error:raise OSError('Private export creation failed') from None
            descriptor=msvcrt.open_osfhandle(handle.Detach(),os.O_WRONLY)
        else:descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except OSError:
        raise ControlDError('Private export could not be created; existing files are never overwritten') from None


def activity_slice(token, account_type, instance, start, end=None, endpoint=None,
                   organization=None, limit=1000):
    if type(limit) is not int or limit < 1:
        raise ControlDError('Decision limit must be positive')
    rows = activity(token, account_type, instance, start, end, endpoint, organization, limit + 1)
    return {'source': 'controld-activity-csv', 'collected_at_utc': utc_now().isoformat(),
            'query_window': {'start_inclusive': start, 'end_inclusive': end},
            'endpoint_id': endpoint, 'truncated': len(rows) > limit, 'rows': rows[:limit]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    credential = parser.add_mutually_exclusive_group()
    credential.add_argument('--token-stdin', action='store_true', help='Read token from one stdin line; never echoed')
    credential.add_argument('--token-vault', action='store_true', help='Read the current Windows user credential')
    credential.add_argument('--token-prompt', action='store_true', help='Hidden one-shot input; not persisted')
    parser.add_argument('--organization', help='Optional sub-organization scope')
    parser.add_argument('--output', help='Optional private JSON file outside this repo; never overwritten')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('inventory', help='Read device/profile inventory')
    policy = commands.add_parser('policy',help='Read the explicitly selected endpoint profile policy')
    policy.add_argument('--endpoint',required=True)
    policy.add_argument('--account-scope',required=True,help='Explicit private local account scope label')
    policy.add_argument('--history',help='Optional private existing/new history directory outside the repo')
    log = commands.add_parser('activity', help='Read a small authenticated activity CSV slice')
    log.add_argument('--account-type', choices=['personal', 'organization'], required=True)
    log.add_argument('--instance', help='Optional explicit label; otherwise discover from account metadata')
    log.add_argument('--start', required=True)
    log.add_argument('--end')
    log.add_argument('--endpoint')
    log.add_argument('--limit', type=int, default=1)
    args = parser.parse_args(argv)
    try:
        if args.token_vault or args.token_prompt:
            from credentials import CredentialStore, CredentialError, prompt_read_token
            try:
                token=CredentialStore().read() if args.token_vault else prompt_read_token()
            except CredentialError:
                raise ControlDError('Secure credential input/read failed; no fallback attempted') from None
            if token is None:
                raise ControlDError('No saved Read credential; use hidden input or explicitly save one')
        else:
            token = (sys.stdin.readline().rstrip('\r\n') if args.token_stdin
                     else os.environ.get('CONTROLD_READ_TOKEN', ''))
        if args.command == 'inventory':
            data = inventory(token, args.organization)
            summary = {'source': data['source'], 'device_count': len(data['devices']),
                       'profile_count': len(data['profiles'])}
        elif args.command == 'activity':
            data = activity_slice(token, args.account_type, args.instance, args.start, args.end,
                                  args.endpoint, args.organization, args.limit)
            summary = {'source': 'controld-activity-csv', 'decision_count': len(data['rows']),
                       'truncated': data['truncated']}
        else:
            data=policy_snapshot(token,args.endpoint,account_scope=args.account_scope,organization=args.organization)
            summary={'source':data['source'],'resources':{k:v['state'] for k,v in data['resources'].items()}}
            if args.history:
                import history
                import analytics
                try:
                    store=history.History(args.history)
                    try: summary['history']=analytics.Analytics(store).record_policy(data)
                    finally: store.close()
                except (history.HistoryError,analytics.QueryError):
                    raise ControlDError('Private policy history write failed; provider state unchanged') from None
        if args.output:
            if args.command=='policy':
                import history
                try: history.private_directory(Path(args.output).absolute().parent)
                except history.HistoryError:
                    raise ControlDError('Policy export requires an owner-private destination') from None
            export_private(args.output, data)
        print(json.dumps(summary))
        return 0
    except ControlDError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
