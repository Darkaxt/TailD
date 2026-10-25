"""Fixed, account-bound recent observations; no provider/network/policy writes."""
import hashlib
from datetime import timedelta
import controld
import desktop_api
import history

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
    end=controld.utc_now();start=end-timedelta(minutes=15);metrics_start=end-timedelta(days=7)
    query={'kind':'dns','view':'facts','start':start.isoformat(),'end':end.isoformat(),
           'scope':{'account':provider['account_scope'],'endpoint':endpoint},'limit':100,
           'order_by':[{'field':'timestamp','direction':'desc'}],**({'search':search} if search else {})}
    store.db.execute('BEGIN')
    try:
        batch=desktop_api.DesktopAPI(store).dispatch('view-query',{'queries':[query]})
        rows=batch['results'][0]['data']['rows']
        questions=sorted({row['question'] for row in rows})
        totals={}
        if questions:
            values=store.db.execute(
                "SELECT d.question,json_extract(d.data,'$.raw.rrType'),min(d.time),count(*) "
                "FROM dns d JOIN sources s ON s.id=d.source WHERE d.time>=? AND d.time<? "
                "AND d.endpoint=? AND json_extract(s.metadata,'$.scope')=? AND d.question IN ("+
                ','.join('?' for _ in questions)+") GROUP BY d.question,json_extract(d.data,'$.raw.rrType')",
                [max(history.instant(metrics_start.isoformat()),store.retention_floor()),history.instant(end.isoformat()),endpoint,provider['account_scope'],*questions])
            totals={(q,t):(first,total) for q,t,first,total in values}
        for row in rows:
            row['first_seen'],row['total']=totals[(row['question'],row['type'])]
    finally:store.db.execute('ROLLBACK')
    return {'account':provider['account_scope'],'endpoint':endpoint,'live_state':live_state,
            'start':query['start'],'end':query['end'],'revision':batch['revision'],
            'metrics_start':metrics_start.isoformat(),'metrics_end':end.isoformat(),
            'rows':batch['results'][0]['data']['rows'],'coverage':batch['results'][0]['coverage']}
