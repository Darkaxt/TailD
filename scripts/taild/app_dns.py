"""Owner-scoped process DNS facts and app diagnosis over existing private history."""
from collections import defaultdict
from bisect import bisect_left,bisect_right
import ipaddress
import json
import ntpath
import re
from fractions import Fraction

import analytics
import history

OPERATIONS=('app-dns-read','app-dns-export','app-dns-delete')


def wire(value):
    """Exact counters and FILETIME identities across the native JSON boundary."""
    if isinstance(value,dict):return {k:str(v) if k in ('inbound','outbound','created') and type(v) is int else wire(v) for k,v in value.items()}
    if isinstance(value,list):return [wire(v) for v in value]
    return value


def path_key(path):
    return ntpath.normcase(ntpath.normpath(path)) if isinstance(path,str) and path else None


def name_key(name):
    return name.rstrip('.').lower() if isinstance(name,str) and name.isascii() else None


def import_batch(store,batch,scope):
    if not isinstance(scope,str) or not scope or not isinstance(batch,dict):raise ValueError('Invalid process DNS scope')
    session=batch.get('session');events=batch.get('events')
    if not isinstance(session,str) or not re.fullmatch('[a-f0-9-]{36}',session) or not isinstance(events,list) or len(events)>8192:
        raise ValueError('Invalid process DNS batch')
    validated=[]
    for fact in events:
        if not isinstance(fact,dict) or fact.get('source')!='windows-dns-client-3008':raise ValueError('Invalid DNS source')
        proc=fact.get('process',{})
        if (type(fact.get('at')) is not int or type(fact.get('sequence')) is not int or fact['sequence']<1 or
            type(fact.get('status')) is not int or not 0<=fact['status']<=0xffffffff or
            type(fact.get('type')) is not int or not 0<=fact['type']<=65535 or
            not isinstance(fact.get('question'),str) or not 1<=len(fact['question'])<=253 or
            any(ord(c)<32 for c in fact['question']) or
            not isinstance(fact.get('results'),str) or len(fact['results'])>8192 or
            type(proc.get('pid')) is not int or type(proc.get('created')) is not int or
            not path_key(proc.get('path')) or len(proc['path'])>32768):raise ValueError('Invalid DNS observation')
        validated.append(fact)
    with store.transaction():
        floor=store._expire();revision=store._bump()
        for fact in validated:
            at=fact['at']
            if at<floor or store._suppressed('app-dns',scope,at):continue
            key=history.digest(['app-dns-v1',scope,session,fact['sequence']])
            store.db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',
                (key,'app-dns',scope,at,at+1,history.packed({**fact,'session':session}),revision))
        return revision


def read(store,body,*,host,provider=None,status=None):
    if not isinstance(body,dict) or set(body)-{'start','end','path','revision'} or not {'start','end'}<=set(body):
        raise analytics.QueryError('Expected app diagnosis window')
    a,b=history.bounds(body['start'],body['end'])
    if b-a>7*86400*1000000:raise analytics.QueryError('Select at most seven days',code='resource-limit')
    selected=body.get('path')
    if selected is not None and (not isinstance(selected,str) or not 1<=len(selected)<=32768):
        raise analytics.QueryError('Invalid application identity')
    store.db.execute('BEGIN')
    revision=store.db.execute('SELECT revision FROM settings').fetchone()[0]
    if body.get('revision') is not None and body['revision']!=revision:
        raise analytics.QueryError('History changed; refresh the app view',code='stale-revision')
    apps={};events=[];key=path_key(selected)
    def app(path):
        normalized=path_key(path)
        if normalized not in apps:
            apps[normalized]={'path':path,'name':ntpath.basename(path) if path else 'Unassigned application',
                'inbound':0,'outbound':0,'queries':0,'blocked':0,'last':None,'hours':{},'domains':{}}
        return apps[normalized]
    traffic=store.db.execute('SELECT app.path,f.inbound,f.outbound,f.time,f.destination FROM traffic f '
        'LEFT JOIN applications app ON app.id=f.application JOIN sources s ON s.id=f.source '
        "WHERE f.time>=? AND f.time<? AND json_extract(s.metadata,'$.scope')=? ORDER BY f.time",
        (a,b,host))
    destinations=defaultdict(lambda:{'inbound':0,'outbound':0});selected_traffic=[]
    for index,row in enumerate(traffic):
        if index>=1000000:raise analytics.QueryError('Narrow the app interval',code='resource-limit')
        path,inc,out,at,ip=row;entry=app(path)
        entry['inbound']+=inc;entry['outbound']+=out
        entry['last']=max(entry['last'] or at,at)
        hour=str(at//3600000000*3600000000)
        bar=entry['hours'].setdefault(hour,{'inbound':0,'outbound':0});bar['inbound']+=inc;bar['outbound']+=out
        if key is not None and path_key(path)==key:
            d=destinations[ip or 'Unknown'];d['inbound']+=inc;d['outbound']+=out
            selected_traffic.append((at,ip,inc,out))
    provider_rows=defaultdict(list)
    # Provider scope is installer/owner-runtime configuration, never supplied by renderer.
    if provider and provider.get('endpoint') and provider.get('account_scope'):
        rows=store.db.execute('SELECT d.time,d.data FROM dns d JOIN sources s ON s.id=d.source '
            "WHERE d.time>=? AND d.time<? AND d.endpoint=? AND json_extract(s.metadata,'$.scope')=? ORDER BY d.time",
            (a-5000000,b+5000000,provider['endpoint'],provider['account_scope']))
        for index,row in enumerate(rows):
            if index>=200000:raise analytics.QueryError('Narrow the DNS interval',code='resource-limit')
            raw=json.loads(row[1])['raw'];provider_rows[name_key(raw.get('question'))].append((row[0],raw))
    provider_times={name:[at for at,_ in rows] for name,rows in provider_rows.items()}
    answers=defaultdict(list)
    for index,row in enumerate(store.db.execute("SELECT data FROM snapshots WHERE kind='app-dns' AND scope=? AND time>=? AND time<? ORDER BY time,id",(host,a-300000000,b))):
        if index>=100000:raise analytics.QueryError('Narrow the DNS interval',code='resource-limit')
        fact=json.loads(row[0])
        if key is not None and path_key(fact['process']['path'])==key and fact['status']==0:
            for address in fact['results'].split(';'):
                try:
                    address=ipaddress.ip_address(address.strip())
                    if isinstance(address,ipaddress.IPv6Address) and address.ipv4_mapped:address=address.ipv4_mapped
                    if not address.is_unspecified and name_key(fact['question']):answers[str(address)].append((fact['at'],name_key(fact['question'])))
                except ValueError:pass
        if fact['at']<a:continue
        entry=app(fact['process']['path']);entry['queries']+=1
        entry['last']=max(entry['last'] or fact['at'],fact['at'])
        question=fact['question'];domain=entry['domains'].setdefault(name_key(question) or question,
            {'name':question,'count':0,'first':fact['at'],'last':fact['at'],'outcome':'unknown','blocked':0,
             'allowed':0,'unknown':0,'evidence':[]})
        canonical=name_key(question);times=provider_times.get(canonical,[])
        candidates=provider_rows.get(canonical,[])[bisect_left(times,fact['at']-5000000):bisect_right(times,fact['at']+5000000)]
        binding=fact.get('binding') or {}
        bound=bool(provider and binding.get('endpoint')==provider.get('endpoint') and
                   binding.get('method')=='active-resolver-point-observation-after-batch' and
                   fact['status'] in (0,9003,9005,9501))
        matches=[raw for _,raw in candidates if bound and str(raw.get('rrType')) in (str(fact['type']),{1:'A',28:'AAAA'}.get(fact['type']))]
        actions={str(r.get('action')) for r in matches}
        outcome=('blocked' if actions=={'0'} else 'allowed' if actions=={'1'} else 'unknown')
        # A negative answer, socket error or status 9003 alone proves no policy block.
        observation={**fact,'outcome':outcome,'provider_matches':len(matches),
            'decision_evidence':'same-endpoint-name-type-time-correlation' if matches else 'unassigned-provider-decision',
            'provider_reasons':sorted({str(m.get('trigger') or '') for m in matches})}
        domain['count']+=1;domain['last']=fact['at'];domain['outcome']=outcome;domain[outcome]+=1
        if len(domain['evidence'])<50:domain['evidence'].append(observation)
        domain['evidence_truncated']=domain['count']>len(domain['evidence'])
        if outcome=='blocked':entry['blocked']+=1
        if key is not None and path_key(fact['process']['path'])==key:events.append(observation)
    for entry in apps.values():
        entry['domains']=sorted(entry['domains'].values(),key=lambda d:(-d['count'],d['name'].lower()))
    values=sorted(apps.values(),key=lambda e:(-(e['inbound']+e['outbound']),e['name'].lower(),path_key(e['path']) or ''))
    selection=apps.get(key) if key is not None else None
    inferred=defaultdict(lambda:{'inbound':Fraction(),'outbound':Fraction()});unmatched=0
    answer_times={ip:[at for at,_ in rows] for ip,rows in answers.items()}
    for at,ip,inc,out in selected_traffic:
        times=answer_times.get(ip,[])
        candidates=sorted({name for _,name in answers.get(ip,[])[bisect_left(times,at-300000000):bisect_right(times,at)]})
        if not candidates:unmatched+=inc+out
        for name in candidates:
            inferred[name]['inbound']+=Fraction(inc,len(candidates));inferred[name]['outbound']+=Fraction(out,len(candidates))
    estimates=[{'domain':name,**{direction:{'numerator':str(value.numerator),'denominator':str(value.denominator)} for direction,value in amounts.items()}}
               for name,amounts in sorted(inferred.items())]
    return {'schema':'taild-app-dns-v1','revision':revision,'start':history.utc(a),'end':history.utc(b),
        'host':host,'apps':[{k:v for k,v in app.items() if k!='domains'} for app in values],'selected':selection,'observations':events,
        'destinations':[{'ip':ip,**v} for ip,v in sorted(destinations.items(),key=lambda kv:-(kv[1]['inbound']+kv[1]['outbound']))],
        'source_status':status or {'state':'unavailable'},'provider_bound':bool(provider),
        'estimated_domains':estimates,'unmatched_bytes':str(unmatched),
        'estimate_method':'app-owned DNS answer IP within preceding 300 seconds; equal 1/N distinct-name allocation; TTL/network-context validity unknown',
        'coverage':'Windows resolver API observations; app-owned encrypted DNS and missing process identities are outside coverage. Provider decisions require a matching active-resolver point observation and remain temporal correlations, not continuous resolver ownership or per-process provider telemetry.'}
