"""Fixed, account-bound recent observations; no provider/network/policy writes."""
import hashlib
from datetime import timedelta
import controld
import desktop_api

OPERATIONS=frozenset(('recent-dns',))

def instance_name(instance):
    return 'recent-'+hashlib.sha256(instance.encode('ascii')).hexdigest()[:32]

def read(store,body,provider,live_state):
    if not provider:raise ValueError('explicit-provider-required')
    if not isinstance(body,dict) or set(body)-{'endpoint','search'}:raise ValueError('invalid-query')
    try:endpoint=controld._identifier(body.get('endpoint',provider['endpoint']))
    except controld.ControlDError:raise ValueError('invalid-query') from None
    search=body.get('search','')
    if not isinstance(search,str) or len(search)>256 or any(ord(c)<32 for c in search):raise ValueError('invalid-query')
    end=controld.utc_now();start=end-timedelta(minutes=15)
    query={'kind':'dns','view':'facts','start':start.isoformat(),'end':end.isoformat(),
           'scope':{'account':provider['account_scope'],'endpoint':endpoint},'limit':100,
           'order_by':[{'field':'timestamp','direction':'desc'}],**({'search':search} if search else {})}
    batch=desktop_api.DesktopAPI(store).dispatch('view-query',{'queries':[query]})
    return {'account':provider['account_scope'],'endpoint':endpoint,'live_state':live_state,
            'start':query['start'],'end':query['end'],'revision':batch['revision'],
            'rows':batch['results'][0]['data']['rows'],'coverage':batch['results'][0]['coverage']}
