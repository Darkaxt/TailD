"""Fixed, account-bound recent observations; no provider/network/policy writes."""
import hashlib
from datetime import timedelta
import analytics
import controld
import history

OPERATIONS=frozenset(('recent-dns','recent-dns-observe'))

def _coverage_summaries(store, sources, starts, end, floor):
    """Exact coverage counts for both horizons, streaming one revision-ordered scan.

    An incomplete attempt is resolved only by complete intervals committed later.
    Keep the canonical coverage semantics without sending every old attempt to
    a view that uses only the partial flag. No observation/history cap is added.
    """
    results=[{'incomplete':True,'sources':[],'detail':'coverage-counts-v1',
        'snapshot_limit':'separate-source-transactions; later corrections possible'} for _ in starts]
    low=max(min(starts),floor)
    deleted=list(store.db.execute("SELECT source,start,end FROM suppressions WHERE kind='dns' AND end>? AND start<?",
        (low,end)))
    for source in sources:
        counts=[dict(source=source,run_count=0,gap_count=0,incomplete_attempt_count=0,
            unresolved_attempt_count=0,deletion_scopes=0) for _ in starts]
        covered=[]
        for left,right,state in store.db.execute('SELECT start,end,state FROM runs WHERE source=? AND end>? AND start<? ORDER BY revision DESC',
                (source,low,end)):
            if state=='complete':covered=store._coverage_union(covered,max(left,low),min(right,end))
            for start,item in zip(starts,counts):
                if right<=start or left>=end:continue
                item['run_count']+=1
                if state!='complete':
                    item['incomplete_attempt_count']+=1
                    if store._coverage_gaps(covered,max(left,start,floor),min(right,end)):
                        item['unresolved_attempt_count']+=1
        for start,item,result in zip(starts,counts,results):
            if not item['run_count']:continue
            item['gap_count']=int(start<floor)+len(store._coverage_gaps(covered,max(start,floor),end))
            item['deletion_scopes']=sum(1 for owner,left,right in deleted
                if (owner is None or owner==source) and right>start and left<end)
            result['sources'].append(item)
    for result in results:
        result['incomplete']=not result['sources'] or any(s['gap_count'] or s['unresolved_attempt_count'] or s['deletion_scopes'] for s in result['sources'])
    return results

def instance_name(instance):
    return 'recent-'+hashlib.sha256(instance.encode('ascii')).hexdigest()[:32]

def read(store,body,provider,live_state):
    if not provider:raise ValueError('explicit-provider-required')
    if not isinstance(body,dict) or set(body)-{'endpoint','search','window'}:raise ValueError('invalid-query')
    try:endpoint=controld._identifier(body.get('endpoint',provider['endpoint']))
    except controld.ControlDError:raise ValueError('invalid-query') from None
    search=body.get('search','')
    if not isinstance(search,str) or len(search)>256 or any(ord(c)<32 for c in search):raise ValueError('invalid-query')
    main=endpoint==provider['endpoint'];window=body.get('window','recent')
    if window not in ('recent','retained') or window=='retained' and not main:raise ValueError('invalid-query')
    history_seconds=7*86400 if main else 7200
    window_seconds=history_seconds if window=='retained' else 7200
    end=controld.utc_now();start=end-timedelta(seconds=window_seconds)
    metrics_start=end-timedelta(seconds=history_seconds)
    scope={'account':provider['account_scope'],'endpoint':endpoint}
    store.db.execute('BEGIN')
    try:
        revision=store.db.execute('SELECT revision FROM settings').fetchone()[0]
        floor=store.retention_floor()
        source_ids=[row[0] for row in store.db.execute("SELECT id FROM sources WHERE kind='dns' "
            "AND json_extract(metadata,'$.scope')=? AND json_extract(metadata,'$.endpoint')=?",
            (provider['account_scope'],endpoint))]
        clause='d.source IN ('+','.join('?' for _ in source_ids)+') AND d.time>=? AND d.time<?' if source_ids else '0'
        parameters=[*source_ids,max(history.instant(start.isoformat()),floor),history.instant(end.isoformat())] if source_ids else []
        if search:
            # Same local domain/decision/endpoint/trigger search contract, with
            # filtering performed by SQLite before the bounded fact page.
            actions=[action for action,outcome in analytics.OUTCOMES.items()
                if search.casefold() in outcome.casefold() or search.casefold() in analytics.OUTCOME_LABELS[outcome].casefold()]
            unknown=search.casefold() in 'unknown'
            clause+=" AND (instr(lower(d.question),?)>0 OR instr(lower(d.endpoint),?)>0 OR "
            clause+="instr(lower(coalesce(json_extract(d.data,'$.raw.trigger'),'')),?)>0 OR "
            clause+="json_extract(d.data,'$.raw.action') IN ("+','.join('?' for _ in actions)+")"
            parameters.extend([search.casefold()]*3+actions)
            if unknown:
                clause+=" OR coalesce(json_extract(d.data,'$.raw.action'),'') NOT IN ("+','.join('?' for _ in analytics.OUTCOMES)+")"
                parameters.extend(analytics.OUTCOMES)
            clause+=')'
        facts=store.db.execute('SELECT d.*,s.metadata FROM dns d JOIN sources s ON s.id=d.source WHERE '+
            clause+' ORDER BY d.time DESC,d.identity DESC,d.ordinal DESC LIMIT 101',parameters)
        rows=list(analytics.Analytics(store)._decode('dns',facts,scope))
        has_more=len(rows)>100;rows=rows[:100]
        questions=sorted({row['question'] for row in rows})
        totals={}
        if questions:
            values=store.db.execute(
                "SELECT d.question,json_extract(d.data,'$.raw.rrType'),min(d.time),count(*) "
                "FROM dns d JOIN sources s ON s.id=d.source WHERE d.time>=? AND d.time<? "
                "AND d.endpoint=? AND json_extract(s.metadata,'$.scope')=? AND d.question IN ("+
                ','.join('?' for _ in questions)+") GROUP BY d.question,json_extract(d.data,'$.raw.rrType')",
                [max(history.instant(metrics_start.isoformat()),floor),history.instant(end.isoformat()),endpoint,provider['account_scope'],*questions])
            totals={(q,t):(first,total) for q,t,first,total in values}
        for row in rows:
            row['first_seen'],row['total']=totals[(row['question'],row['type'])]
        metrics_coverage,coverage=_coverage_summaries(store,source_ids,
            [history.instant(metrics_start.isoformat()),history.instant(start.isoformat())],history.instant(end.isoformat()),floor)
    finally:store.db.execute('ROLLBACK')
    return {'account':provider['account_scope'],'endpoint':endpoint,'live_state':live_state,
            'start':start.isoformat(),'end':end.isoformat(),'revision':revision,
            'metrics_start':metrics_start.isoformat(),'metrics_end':end.isoformat(),
            'rows':rows,'has_more':has_more,'window_seconds':window_seconds,'history_seconds':history_seconds,'is_main':main,
            'metrics_coverage':metrics_coverage,
            'coverage':{'dns':coverage,'traffic':{'incomplete':True,'sources':[],
                'snapshot_limit':'not requested for DNS-only query'}}}
