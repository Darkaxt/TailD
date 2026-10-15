"""Revision-consistent on-demand analytics over private TailD facts; no source writes."""
from collections import defaultdict
from bisect import bisect_right
import base64
import json
import math
import binascii
import subprocess
import sys
import argparse
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

import history
import join
import ingestion
import controld

VERSION='taild-metrics-v3'
OUTCOME_VERSION='controld-action-v1'
# https://docs.controld.com/docs/log-field-reference, Control D action enum.
OUTCOMES={'-1':'failed','0':'block','1':'allow','2':'redirect','3':'redirect'}
CORRELATION_VERSION='same-endpoint-answer-ip-preceding-context-v1'
CONTEXT_FIELDS=frozenset(('source','captured_at_utc','observed_until_utc','coverage_method',
    'node_id','user_id','os','backend_state','dns_accepted','local_override','resolver_endpoint',
    'exit_node_id','exit_node_ip','portal_mode','endpoint_exclusivity','magic_dns_enabled',
    'magic_dns_suffix','split_dns_routes','search_domains','resolver_event_coverage','resolver_applied','profile_id',
    'capture_consistency'))
COMMON_FIELDS={'id':str,'timestamp':int,'source':str,'scope':str}
DNS_FIELDS={'endpoint':str,'question':str,'type':str,'action':str,'reason':str,'reason_value':str,'provider_country':str,'provider_asn':str,
            'profile':str,'outcome':str,'protocol':str,'client':str}
TRAFFIC_FIELDS={'application':str,'application_path':str,'destination_ip':str,'destination_port':int,
                'protocol_raw':int,'inbound_bytes':int,'outbound_bytes':int,'total_bytes':int,
                'correlation_state':str,'context_state':str}
TRAFFIC_FIELDS.update({'destination_country':str,'destination_asn':str})
SNAPSHOT_FIELDS={'node_id':str,'user_id':str,'resolver_endpoint':str,'backend_state':str,'exit_node_id':str,
                 'dns_accepted':bool,'local_override':bool,'portal_mode':bool,'observed_end':int}


class QueryError(RuntimeError):
    def __init__(self, message, *, code='invalid-query'):
        self.code = code
        super().__init__(message)


def answer_metadata(raw):
    """Documented answer metadata is usable only for one unambiguous answer IP."""
    try:
        addresses,unsupported=join._answers(raw)
    except join.JoinError:
        addresses,unsupported=set(),True
    if unsupported or len(addresses)!=1:
        return {'answer_country':None,'answer_asn':None}
    country,asn=raw.get('answerCountryCode'),raw.get('answerASN')
    return {'answer_country':country if isinstance(country,str) and re.fullmatch('[A-Z]{2}',country) else None,
            'answer_asn':asn if isinstance(asn,str) and asn.isascii() and asn.isdecimal() else None}


def provider_metadata(raw):
    country,asn=raw.get('answerCountryCode'),raw.get('answerASN')
    return {'provider_country':country if isinstance(country,str) and re.fullmatch('[A-Z]{2}',country) else None,
            'provider_asn':asn if isinstance(asn,str) and asn.isascii() and asn.isdecimal() else None}


def unsupported_answer(raw):
    try:
        return join._answers(raw)[1]
    except join.JoinError:
        return True


def capture_context(cli):
    """Whitelisted supported local READs; no preferences/peer-map export or changes."""
    options={'creationflags':subprocess.CREATE_NO_WINDOW} if sys.platform=='win32' else {}
    def read(*args):
        return json.loads(subprocess.check_output([str(cli),*args],stderr=subprocess.DEVNULL,**options))
    try:
        status=read('status','--json')
        prefs=read('debug','prefs')
        dns=read('dns','status','--json')
        local=read('debug','localapi','GET','/localapi/v0/local-dns')
        after_status=read('status','--json')
        after_prefs=read('debug','prefs')
        after_dns=read('dns','status','--json')
        after_local=read('debug','localapi','GET','/localapi/v0/local-dns')
        def signature(s,p,d,l):
            node=s.get('Self') or {}
            return [s.get('BackendState'),[node.get(k) for k in ('ID','UserID','OS')],
                    [p.get(k) for k in ('CorpDNS','ExitNodeID','ExitNodeIP')],
                    [d.get(k) for k in ('CurrentTailnet','SplitDNSRoutes','SearchDomains')],
                    [l.get(k) for k in ('ProfileID','Configured','Endpoint','Applied','CaptivePortal')]]
        if signature(status,prefs,dns,local)!=signature(after_status,after_prefs,after_dns,after_local):
            raise QueryError('Local context changed during capture; observation discarded')
        node=status.get('Self') or {}
        resolver=urlsplit(local.get('Endpoint',''))
        endpoint=resolver.path.removeprefix('/') if resolver.scheme=='https' and resolver.netloc=='dns.controld.com' and not resolver.query and not resolver.fragment else None
        if endpoint:
            endpoint=join._endpoint(endpoint)
        tailnet=dns.get('CurrentTailnet') or {}
        routes=[]
        for suffix,servers in dns.get('SplitDNSRoutes',{}).items():
            routes.append({'suffix':suffix,'resolvers':[r['Addr'] if isinstance(r,dict) else r for r in servers]})
        return {'source':'taildns-cli-readonly','captured_at_utc':controld.utc_now().isoformat(),
            'coverage_method':'point-observation','node_id':node.get('ID'),
            'user_id':str(node['UserID']) if node.get('UserID') is not None else None,'os':node.get('OS'),
            'profile_id':local.get('ProfileID'),'backend_state':status.get('BackendState'),
            'dns_accepted':prefs.get('CorpDNS'),'local_override':local.get('Configured'),
            'resolver_endpoint':endpoint,'resolver_applied':local.get('Applied'),
            'exit_node_id':prefs.get('ExitNodeID') or None,'exit_node_ip':prefs.get('ExitNodeIP') or None,
            'portal_mode':local.get('CaptivePortal'),'magic_dns_enabled':tailnet.get('MagicDNSEnabled'),
            'magic_dns_suffix':tailnet.get('MagicDNSSuffix'),'split_dns_routes':routes,
            'search_domains':dns.get('SearchDomains',[]),'resolver_event_coverage':'unavailable',
            'endpoint_exclusivity':'unverified','capture_consistency':'separate-local-api-reads'}
    except (OSError,subprocess.CalledProcessError,ValueError,TypeError,KeyError,AttributeError,join.JoinError):
        raise QueryError('Could not read compatible local TailDNS context; no settings changed') from None


class Analytics:
    """One owning store, fixed-query source reads, backend aggregation and bounded pages."""
    def __init__(self,store):
        self.store=store

    def record_policy(self,data):
        fields={'source','account_scope','endpoint','profile','captured_at_utc','consistency',
                'historical_rule_causality','resources'}
        if (not isinstance(data,dict) or set(data)!=fields or data['source']!='controld-api-readonly'
                or data['consistency']!='separate-api-reads' or data['historical_rule_causality']!='not-established'):
            raise QueryError('Expected a point-observed read-only Control D policy snapshot')
        for field in ('account_scope','endpoint','profile'):
            try: controld._identifier(data[field])
            except controld.ControlDError:
                raise QueryError('Explicit policy account/endpoint/profile scope required') from None
        resources=data['resources']
        allowed={r[0] for r in controld.POLICY_READS}|{'account','endpoints','profiles','clients','restriction_catalog'}
        states={'available','unavailable','denied','rate-limited','stale','incompatible','incomplete'}
        if (not isinstance(resources,dict) or set(resources)-allowed or
                any(not isinstance(v,dict) or v.get('state') not in states for v in resources.values())):
            raise QueryError('Unsupported policy resource or capability state')
        a=history.instant(data['captured_at_utc'])
        scope=data['account_scope']
        key=history.digest(['policy',scope,a,data])
        with self.store.transaction():
            self.store._expire()
            if a<self.store.db.execute('SELECT expiry_floor FROM settings').fetchone()[0]:
                raise QueryError('Policy observation is outside retained history')
            if self.store.db.execute("SELECT 1 FROM suppressions WHERE kind='policy' AND (source IS NULL OR source=?) AND end>? AND start<? LIMIT 1",(scope,a,a+1)).fetchone():
                return {'suppressed':True}
            existing=self.store.db.execute('SELECT revision FROM snapshots WHERE id=?',(key,)).fetchone()
            if existing:
                return {'id':key,'revision':existing[0]}
            revision=self.store._bump()
            self.store.db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)',
                                  (key,'policy',scope,a,a+1,history.packed(data),revision))
        return {'id':key,'revision':revision}

    def record_context(self,scope,data):
        if not isinstance(scope,str) or not scope or not isinstance(data,dict):
            raise QueryError('Explicit context host scope and object required')
        if set(data)-CONTEXT_FIELDS or data.get('source')!='taildns-cli-readonly':
            raise QueryError('Unsupported context fields/source')
        a=history.instant(data.get('captured_at_utc'))
        b=history.instant(data['observed_until_utc']) if data.get('observed_until_utc') else a+1
        if b<=a or (b>a+1 and data.get('coverage_method')!='observed-change-stream'):
            raise QueryError('Context interval needs observed continuity evidence')
        for field in ('dns_accepted','local_override','portal_mode'):
            if data.get(field) is not None and type(data[field]) is not bool:
                raise QueryError('Context requires explicit DNS/portal state')
        for field in CONTEXT_FIELDS-{'dns_accepted','local_override','portal_mode','resolver_applied','magic_dns_enabled','split_dns_routes','search_domains'}:
            if data.get(field) is not None and (not isinstance(data[field],str) or len(data[field])>1024):
                raise QueryError('Invalid context text field')
        for field in ('resolver_applied','magic_dns_enabled'):
            if data.get(field) is not None and type(data[field]) is not bool:
                raise QueryError('Invalid context configuration flag')
        domains=data.get('search_domains',[])
        routes=data.get('split_dns_routes',[])
        if not isinstance(domains,list) or len(domains)>1024 or any(not isinstance(d,str) or len(d)>1024 for d in domains):
            raise QueryError('Invalid context search domains')
        if not isinstance(routes,list) or len(routes)>1024:
            raise QueryError('Invalid context routes')
        for route in routes:
            if not isinstance(route,dict) or set(route)!={'suffix','resolvers'} or not isinstance(route['suffix'],str) or not isinstance(route['resolvers'],list) or len(route['resolvers'])>1024 or any(not isinstance(r,str) or len(r)>1024 for r in route['resolvers']):
                raise QueryError('Invalid context route fields')
        key=history.digest(['context',scope,a,b,data])
        with self.store.transaction():
            self.store._expire()
            if b<=self.store.db.execute('SELECT expiry_floor FROM settings').fetchone()[0]:
                raise QueryError('Context is outside retained history')
            if self.store.db.execute("SELECT 1 FROM suppressions WHERE kind='context' AND (source IS NULL OR source=?) AND end>? AND start<? LIMIT 1",(scope,a,b)).fetchone():
                return {'suppressed':True}
            next_time=self.store.db.execute("SELECT min(time) FROM snapshots WHERE kind='context' AND scope=? AND time>?",(scope,a)).fetchone()[0]
            if next_time is not None:
                b=min(b,next_time)
            self.store.db.execute("UPDATE snapshots SET end=? WHERE kind='context' AND scope=? AND time<? AND end>?",(a,scope,a,a))
            revision=self.store._bump()
            self.store.db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',
                                 (key,'context',scope,a,b,history.packed(data),revision))
        return {'id':key,'revision':revision}

    def delete_snapshots(self,kind,start,end,*,scope):
        if kind not in ('context','policy') or not isinstance(scope,str) or not scope:
            raise QueryError('Explicit snapshot kind/scope required')
        a,b=history.bounds(start,end)
        with self.store.transaction():
            self.store._bump()
            self.store.db.execute('INSERT INTO suppressions VALUES(?,?,?,?,NULL)',(kind,scope,a,b))
            self.store.db.execute('DELETE FROM snapshots WHERE kind=? AND scope=? AND end>? AND time<?',(kind,scope,a,b))

    def _load(self,kind,a,b,scope,*,allow_stream=False):
        if kind in ('context','policy'):
            field='host' if kind=='context' else 'account'
            clause,params='kind=? AND end>? AND time<?',[kind,a,b]
            if scope.get(field):
                clause+=' AND scope=?'
                params.append(scope[field])
            rows=self.store.db.execute('SELECT * FROM snapshots WHERE '+clause+' ORDER BY time,id LIMIT 100001', params).fetchall()
            if len(rows)>100000: raise QueryError('Snapshot budget exceeded; narrow the selected scope',code='resource-limit')
            result=[dict(json.loads(r['data']),id=r['id'],timestamp=r['time'],scope=r['scope'],observed_end=r['end']) for r in rows]
            return [r for r in result if (not scope.get('device') or r.get('node_id')==scope['device'])
                    and (not scope.get('endpoint') or r.get('resolver_endpoint' if kind=='context' else 'endpoint')==scope['endpoint'])]
        clause,params='f.time>=? AND f.time<?',[a,b]
        field='host' if kind=='traffic' else 'account'
        if scope.get(field):
            clause+=" AND json_extract(s.metadata,'$.scope')=?"
            params.append(scope[field])
        if kind=='dns' and scope.get('endpoint'):
            clause+=' AND f.endpoint=?'
            params.append(scope['endpoint'])
        sql=(f'SELECT f.*,s.metadata'+(',app.path' if kind=='traffic' else '')+
             f' FROM {kind} f JOIN sources s ON s.id=f.source'+
             (' LEFT JOIN applications app ON app.id=f.application' if kind=='traffic' else '')+
             ' WHERE '+clause+' ORDER BY f.time,f.source,f.identity'+(',f.ordinal' if kind=='dns' else ''))
        if allow_stream and kind=='traffic':
            count=self.store.db.execute('SELECT count(*) FROM ('+sql+' LIMIT 100001)',params).fetchone()[0]
            if count>100000:
                # Reiterable within this read transaction, not a cross-revision
                # cache. SQLite supplies one row at a time for broad aggregates.
                compact_sql=('SELECT f.source,f.identity,f.time,f.application,f.destination,f.port,f.inbound,f.outbound,app.path,'
                    "json_extract(f.data,'$.protocol_raw') protocol_raw,json_extract(s.metadata,'$.scope') scope "
                    'FROM traffic f JOIN sources s ON s.id=f.source LEFT JOIN applications app ON app.id=f.application '
                    'WHERE '+clause+' ORDER BY f.time,f.source,f.identity')
                return lambda with_identity=True:self._decode(kind,self.store.db.execute(compact_sql,params),scope,
                    compact=True,with_identity=with_identity)
        rows=self.store.db.execute(sql+' LIMIT 100001',params).fetchall()
        if len(rows)>100000:
            raise QueryError('Fact budget exceeded; narrow the UTC interval or source scope',code='resource-limit')
        return list(self._decode(kind,rows,scope))

    def _decode(self,kind,rows,scope,*,compact=False,with_identity=True):
        for row in rows:
            metadata={'scope':row['scope']} if compact else json.loads(row['metadata'])
            required=scope.get('host' if kind=='traffic' else 'account')
            if required and metadata['scope']!=required:
                continue
            if kind=='dns' and scope.get('endpoint') and row['endpoint']!=scope['endpoint']:
                continue
            fact={'protocol_raw':row['protocol_raw']} if compact else json.loads(row['data'])
            value={'id':history.digest([kind,row['source'],row['identity'],row['ordinal'] if kind=='dns' else None]) if with_identity else None,
                   'timestamp':row['time'],'source':row['source'],'scope':metadata['scope'],'fact':fact}
            if kind=='traffic':
                value.update(application=row['application'] if row['path'] else None,application_path=row['path'],
                    destination_ip=row['destination'],destination_port=row['port'],protocol_raw=fact['protocol_raw'],
                    inbound_bytes=row['inbound'],outbound_bytes=row['outbound'],total_bytes=row['inbound']+row['outbound'])
            else:
                raw=fact['raw']
                value.update(endpoint=row['endpoint'],question=row['question'],type=raw.get('rrType'),
                             action=raw.get('action'),reason=raw.get('trigger'),profile=raw.get('profileId'),outcome=OUTCOMES.get(raw.get('action'),'unknown'),
                             protocol=raw.get('protocol'),reason_value=raw.get('triggerValue'),client=raw.get('clientId'),
                             **answer_metadata(raw),**provider_metadata(raw))
            yield value

    def _correlations(self,traffic,dns,contexts,age,scope):
        return list(self._iter_correlations(traffic,dns,contexts,age,scope))

    def _iter_correlations(self,traffic,dns,contexts,age,scope):
        by_ip=defaultdict(list)
        for decision in dns:
            try:
                answers,unsupported=join._answers(decision['fact']['raw'])
            except join.JoinError:
                answers,unsupported=set(),True
            decision['unsupported_answers']=unsupported
            for address in answers:
                by_ip[address].append(decision)
        ordered=sorted(contexts,key=lambda c:c['timestamp'])
        starts=[c['timestamp'] for c in ordered]
        ends=[]
        for c in ordered:ends.append(max(ends[-1] if ends else 0,c['observed_end']))
        for traffic_row in traffic:
            row=dict(traffic_row)
            t=row['timestamp']
            observed=[];index=bisect_right(starts,t)-1
            while index>=0 and ends[index]>t:
                c=ordered[index]
                if c['scope']==row['scope'] and t<c['observed_end']:observed.append(c)
                index-=1
            # Conflicting captures never choose an arbitrary binding.
            context=observed[0] if len(observed)==1 else None
            usable=bool(row['application_path'] and row['destination_ip'])
            bound=bool(context and context.get('backend_state')=='Running' and context.get('node_id') and context.get('user_id')
                       and context.get('dns_accepted') is True and context.get('local_override') is True
                       and context.get('resolver_applied') is True and context.get('portal_mode') is False
                       and context.get('resolver_endpoint') and (not scope.get('device') or scope['device']==context['node_id']))
            candidates=[]
            if usable and bound:
                for d in by_ip.get(row['destination_ip'],[]):
                    delta=t-d['timestamp']
                    if d['endpoint']==context['resolver_endpoint'] and 0<=delta<=age*1000000 and d['timestamp']>=context['timestamp']:
                        candidates.append({'decision_id':d['id'],'question':d['question'],'endpoint':d['endpoint'],
                            'age_microseconds':delta,'context_id':context['id'],'method':CORRELATION_VERSION,
                            'ttl_validity':'unknown',**{f:d.get(f) for f in (*DNS_FIELDS,'answer_country','answer_asn')}})
            state='unusable' if not usable else 'unmatched' if not candidates else 'unique-candidate' if len(candidates)==1 else 'ambiguous'
            row.update(correlation_state=state,candidates=candidates,
                context_state='observed-binding' if bound else 'historical-binding-unknown',
                device=context.get('node_id') if bound else None,
                deterministic_domain_attribution=False,candidate_origin_unproven=True,
                resolver_route='event-coverage-unavailable',correlation_version=CORRELATION_VERSION)
            row['destination_country']=candidates[0]['answer_country'] if len(candidates)==1 else None
            row['destination_asn']=candidates[0]['answer_asn'] if len(candidates)==1 else None
            yield row

    def batch(self,requests,*,expected_revision=None,on_result=None):
        if not isinstance(requests,list) or not 1<=len(requests)<=16:
            raise QueryError('Expected 1 to 16 typed queries')
        for request in requests:
            self._validate(request)
        self.store.db.execute('BEGIN')
        try:
            revision=self.store.db.execute('SELECT revision FROM settings').fetchone()[0]
            if expected_revision is not None and (type(expected_revision) is not int or revision!=expected_revision):
                raise QueryError('History changed; explicitly refresh the view',code='stale-revision')
            # Preparation belongs solely to this read transaction. Dashboard
            # summary, series and application groups share the same canonical
            # inputs/candidates, but keep their own predicates and aggregates.
            prepared={'requests':requests,'identity':any(self._requires_identity(q) for q in requests)}
            results=[None]*len(requests)
            # Provider decisions are independent of traffic correlation, but all
            # progress belongs to this one SQLite snapshot. Preserve final order.
            order=sorted(range(len(requests)),key=lambda i:0 if requests[i]['kind']=='dns' and requests[i]['view']=='series' else
                         1 if requests[i]['kind']=='dns' else 2) if on_result else range(len(requests))
            for index in order:
                result=self._query(requests[index],revision,prepared);results[index]=result
                if on_result:on_result({'revision':revision,'aggregation_version':VERSION,
                    'correlation_version':CORRELATION_VERSION,'index':index,'result':result})
            return {'revision':revision,'aggregation_version':VERSION,'correlation_version':CORRELATION_VERSION,'results':results}
        finally:
            self.store.db.execute('ROLLBACK')

    @staticmethod
    def _fields(kind):
        return COMMON_FIELDS | (DNS_FIELDS if kind=='dns' else TRAFFIC_FIELDS | DNS_FIELDS
            if kind in ('traffic','correlations') else SNAPSHOT_FIELDS if kind=='context' else {'profile':str,'endpoint':str})

    @staticmethod
    def _requires_identity(request):
        def contains(node):
            return bool(node and (node.get('field')=='id' or any(contains(c) for c in node.get('all',node.get('any',[])))))
        return contains(request.get('where')) or 'id' in request.get('group_by',[])

    def _validate(self,request):
        allowed={'kind','view','start','end','scope','max_age_seconds','where','search','group_by','order_by','limit','cursor','bin_seconds','anchor_id'}
        if not isinstance(request,dict) or set(request)-allowed or not {'kind','view','start','end'}<=request.keys():
            raise QueryError('Expected an allowlisted typed query object')
        kind=request['kind']
        if kind not in ('traffic','dns','correlations','context','policy') or request['view'] not in ('summary','facts','groups','series','health'):
            raise QueryError('Unsupported fact kind/view')
        if request['view'] in ('summary','series') and kind not in ('traffic','correlations','dns'):
            raise QueryError('Snapshots support facts/groups/health, not traffic metrics')
        if 'group_by' in request and request['view']!='groups' or 'bin_seconds' in request and request['view']!='series':
            raise QueryError('Query option is unsupported for this view')
        if 'order_by' in request and request['view'] not in ('facts','groups') or 'limit' in request and request['view']!='facts':
            raise QueryError('Ordering/pagination option is unsupported for this view')
        try:
            a,b=history.bounds(request['start'],request['end'])
        except history.HistoryError:
            raise QueryError('Expected ascending RFC 3339 UTC bounds') from None
        scope=request.get('scope',{})
        if not isinstance(scope,dict) or set(scope)-{'host','account','endpoint','device'} or any(not isinstance(v,str) or not v or len(v)>512 for v in scope.values()):
            raise QueryError('Unsupported or invalid scope')
        if kind in ('dns','policy') and scope.get('device'):
            raise QueryError('Provider endpoint does not prove a physical device; use account/endpoint scope')
        age=request.get('max_age_seconds',300)
        if type(age) is not int or not 1<=age<=86400:
            raise QueryError('Analytical correlation age must be 1 to 86400 seconds')
        for field,default,maximum in (('limit',100,10000),('bin_seconds',60,86400)):
            value=request.get(field,default)
            if type(value) is not int or not 1<=value<=maximum:
                raise QueryError('Invalid query resource bound')
        if request['view']=='series' and math.ceil((b-a)/1000000/request.get('bin_seconds',60))+1>10000:
            raise QueryError('Chart bin budget exceeded')
        search=request.get('search','')
        if not isinstance(search,str) or len(search)>1024:
            raise QueryError('Expected bounded text search')
        fields=self._fields(kind)
        groups=request.get('group_by',[])
        if not isinstance(groups,list) or len(groups)>4 or any(not isinstance(f,str) or f not in fields for f in groups) or len(set(groups))!=len(groups):
            raise QueryError('Unsupported group fields')
        if kind in ('traffic','correlations') and any(f in DNS_FIELDS for f in groups):
            raise QueryError('DNS candidate fanout grouping is not a byte domain; use inferred-domain metrics')
        orders=request.get('order_by',[])
        order_fields=fields|({'count':int} if request['view']=='groups' else {})
        if not isinstance(orders,list) or len(orders)>4 or any(not isinstance(o,dict) or set(o)!={'field','direction'} or not isinstance(o['field'],str) or o['field'] not in order_fields or o['direction'] not in ('asc','desc') for o in orders):
            raise QueryError('Unsupported order fields/direction')
        if kind in ('traffic','correlations') and any(o['field'] in DNS_FIELDS for o in orders):
            raise QueryError('Cannot order traffic by multiple candidate values')
        cursor=request.get('cursor')
        if cursor is not None and (not isinstance(cursor,str) or len(cursor)>4096 or request['view']!='facts'):
            raise QueryError('Invalid cursor')
        if 'anchor_id' in request and (request['view']!='facts' or request.get('cursor') or
                not isinstance(request['anchor_id'],str) or not re.fullmatch('[a-f0-9]{64}',request['anchor_id'])):
            raise QueryError('Invalid refresh anchor')
        self._validate_predicate(request.get('where'),fields)

    def _validate_predicate(self,node,fields,depth=0,budget=None):
        if node is None:
            return
        budget=[0] if budget is None else budget
        budget[0]+=1
        if budget[0]>256:
            raise QueryError('Predicate node budget exceeded')
        if not isinstance(node,dict) or depth>8:
            raise QueryError('Invalid or overly deep predicate')
        if set(node) in ({'all'},{'any'}):
            children=next(iter(node.values()))
            if not isinstance(children,list) or not 1<=len(children)<=16:
                raise QueryError('Invalid predicate group')
            for child in children:
                self._validate_predicate(child,fields,depth+1,budget)
            return
        if set(node)!={'field','op','value'} or not isinstance(node['field'],str) or node['field'] not in fields or node['op'] not in ('eq','ne','in','contains','gt','gte','lt','lte'):
            raise QueryError('Unsupported predicate field/operator')
        target=fields[node['field']]
        values=node['value'] if node['op']=='in' else [node['value']]
        if not isinstance(values,list) or not 1<=len(values)<=100 or any(v is not None and type(v) is not target for v in values):
            raise QueryError('Predicate value has the wrong type')
        if node['op']=='contains' and target is not str or node['op'] in ('gt','gte','lt','lte') and target is not int:
            raise QueryError('Operator unavailable for field type')
        if any(isinstance(v,str) and len(v)>1024 for v in values):
            raise QueryError('Predicate text budget exceeded')

    def _coverage(self,kind,a,b,scope,where=None,*,cache=None):
        cache={} if cache is None else cache
        field='host' if kind=='traffic' else 'account'
        source_key=('sources',kind)
        if source_key not in cache:cache[source_key]=list(self.store.db.execute('SELECT id,metadata FROM sources WHERE kind=?',(kind,)))
        sources=[r[0] for r in cache[source_key]
                 if (not scope.get(field) or json.loads(r[1])['scope']==scope[field])
                 and (kind!='dns' or not scope.get('endpoint') or json.loads(r[1]).get('endpoint')==scope['endpoint'])
                 and self._source_matches({'source':r[0],'scope':json.loads(r[1])['scope'],
                                           'endpoint':json.loads(r[1]).get('endpoint')},where,kind)]
        detail=[]
        for source in sources:
            item=self.store._coverage(kind,a,b,source,cache=cache)
            detail.extend(item['sources'])
        return {'incomplete':not detail or any(d['gaps'] or d['deletion_scopes'] or any(not x['resolved'] for x in d['incomplete_attempts']) for d in detail),
                'sources':detail,'snapshot_limit':'separate-source-transactions; later corrections possible'}

    @staticmethod
    def _source_matches(row,node,kind):
        if node is None: return True
        if 'all' in node: return all(Analytics._source_matches(row,c,kind) for c in node['all'])
        if 'any' in node: return any(Analytics._source_matches(row,c,kind) for c in node['any'])
        if node['field'] not in ({'source','scope','endpoint'} if kind=='dns' else {'source','scope'}): return True
        return Analytics._matches(row,node)

    @staticmethod
    def _aggregate_family(request):
        return (*history.bounds(request['start'],request['end']),history.packed(request.get('scope',{})),
                request.get('max_age_seconds',300),history.packed(request.get('where')),request.get('search',''))

    def _unbound_aggregates(self,request,contexts,requests):
        """Covering-index reduction when no observed context can produce candidates.

        This is not a cached/approximate rollup. Aggregate rows carry exact weights
        and are consumed only inside the caller's read transaction. Evidence/id,
        candidate filters and bound contexts keep the normal fact evaluator.
        """
        if request['view'] not in ('summary','series','groups') or request.get('search') or request.get('scope',{}).get('device'):
            return None
        if any(c.get('backend_state')=='Running' and c.get('node_id') and c.get('user_id')
               and c.get('dns_accepted') is True and c.get('local_override') is True
               and c.get('resolver_applied') is True and c.get('portal_mode') is False
               and c.get('resolver_endpoint') for c in contexts):return None
        where=request.get('where')
        if where and not (set(where)=={'field','op','value'} and where['field']=='application' and where['op']=='eq'):
            return None
        siblings=[q for q in requests if q['kind'] in ('traffic','correlations') and self._aggregate_family(q)==self._aggregate_family(request)]
        if any(q['view'] not in ('summary','series','groups') for q in siblings):return None
        columns={'application','application_path','destination_ip','destination_port','protocol_raw','source','scope'}
        derived={'correlation_state','context_state','device','destination_country','destination_asn'}
        fields={'application','application_path'}
        # Application-only rankings need presence for exact usable/unmatched
        # counts, not one intermediate group per remote IP. Summaries retain
        # the full destination domain for their independent metrics.
        fields.add('destination_ip' if any(q['view']=='summary' or 'destination_ip' in q.get('group_by',[]) for q in siblings)
                   else '_destination_observed')
        for q in siblings:
            if any(f not in columns and f not in derived for f in q.get('group_by',[])):return None
            fields.update(f for f in q.get('group_by',[]) if f in columns)
        a,b=history.bounds(request['start'],request['end']);scope=request.get('scope',{})
        clause='time>=? AND time<?';params=[a,b]
        if scope.get('host'):clause+=" AND source IN (SELECT id FROM sources WHERE json_extract(metadata,'$.scope')=?)";params.append(scope['host'])
        steps=[q.get('bin_seconds',60) for q in siblings if q['view']=='series']
        step=math.gcd(*steps)*1000000 if steps else None
        # Hash narrow canonical values rather than sorting every wide fact into
        # SQLite's temporary B-tree. Paths are resolved once per executable;
        # timestamp/source/identity ordering is retained only per aggregate.
        fields.discard('application_path')
        fields.discard('application')
        if 'scope' in fields:fields.discard('scope');fields.add('source')
        fields=sorted(fields)
        columns={'destination_ip':'destination','destination_port':'port',
            'protocol_raw':"json_extract(data,'$.protocol_raw')",'source':'source',
            '_destination_observed':"destination IS NOT NULL AND destination!=''"}
        sql=('SELECT time,source,identity,inbound,outbound,'+','.join(columns[field] for field in fields)+
             ' FROM traffic INDEXED BY traffic_application_time WHERE application IS ? AND '+clause)
        def reduced():
            applications=dict(self.store.db.execute('SELECT id,path FROM applications'))
            sources={r[0]:json.loads(r[1])['scope'] for r in self.store.db.execute("SELECT id,metadata FROM sources WHERE kind='traffic'")}
            values=[]
            # Exact executable/range seeks keep the temporary grouping local to
            # one executable, instead of spilling millions of wide rows. This
            # also keeps a short selected interval a range seek, not a full scan.
            for application,path in [*applications.items(),(None,None)]:
                if where and (application if path else None)!=where['value']:continue
                aggregates={};cursor=self.store.db.execute(sql,[application,*params]);cursor.row_factory=None
                for record in cursor:
                    timestamp,source,identity,incoming,outgoing=record[:5]
                    key=record[5:]+((timestamp//step,) if step else ())
                    value=aggregates.get(key)
                    if value is None:
                        aggregates[key]=[(timestamp,source,identity),timestamp,1,incoming,outgoing]
                    else:
                        value[2]+=1;value[3]+=incoming;value[4]+=outgoing
                        if timestamp>value[1]:value[1]=timestamp
                        if timestamp<=value[0][0]:
                            first=(timestamp,source,identity)
                            if first<value[0]:value[0]=first
                for key,(first,timestamp,weight,incoming,outgoing) in aggregates.items():
                    row=dict(zip(fields,key));row.update(application=application if path else None,application_path=path)
                    if 'source' in row:row['scope']=sources[row['source']]
                    destination=row.pop('_destination_observed',row.get('destination_ip'))
                    row.update(timestamp=timestamp,inbound_bytes=incoming,outbound_bytes=outgoing,total_bytes=incoming+outgoing,
                        _weight=weight,_first=first,candidates=[],device=None,
                        correlation_state='unmatched' if path and destination else 'unusable',
                        context_state='historical-binding-unknown',destination_country=None,destination_asn=None)
                    values.append(row)
            return sorted(values,key=lambda row:row['_first'])
        prepared_rows=None
        def prepared():
            nonlocal prepared_rows
            if prepared_rows is None:prepared_rows=reduced()
            return iter(prepared_rows)
        return prepared

    def _query(self,request,revision,prepared=None):
        kind=request.get('kind')
        view=request.get('view')
        if kind not in ('traffic','dns','correlations','context','policy') or view not in ('summary','facts','groups','series','health'):
            raise QueryError('Unsupported fact kind/view')
        a,b=history.bounds(request['start'],request['end'])
        scope=request.get('scope',{})
        age=request.get('max_age_seconds',300)
        cache=prepared if prepared is not None else {}
        contexts=[];reduced=None
        if kind in ('traffic','correlations') and view!='health':
            context_key=('context-input',a-age*1000000,b,scope.get('host'))
            if context_key not in cache:
                cache[context_key]=self._load('context',a-age*1000000,b,{'host':scope['host']} if scope.get('host') else {})
            contexts=cache[context_key]
            reduced=self._unbound_aggregates(request,contexts,cache.get('requests',[request]))
        key=('traffic' if kind=='correlations' else kind,view=='health',a,b,age,history.packed(scope))
        if kind in ('traffic','correlations'):
            key+= (view=='facts',history.packed(request.get('where')),request.get('search',''))
        if key not in cache:
            dns_key=('dns-input',a-age*1000000,b,history.packed({k:v for k,v in scope.items() if k in ('account','endpoint')}))
            # Unbound application/series reductions cannot produce DNS
            # candidates. Only summaries need independent provider metrics.
            summary_needed=any(q['view']=='summary' and self._aggregate_family(q)==self._aggregate_family(request)
                               for q in cache.get('requests',[request]))
            if view!='health' and (kind=='dns' or kind in ('traffic','correlations') and (not reduced or summary_needed)):
                if dns_key not in cache:cache[dns_key]=self._load('dns',a-age*1000000,b,scope)
                dns=cache[dns_key]
            else:dns=[]
            traffic=[] if reduced else self._load('traffic',a,b,scope,allow_stream=view in ('summary','groups','series')) if view!='health' and kind in ('traffic','correlations') else []
            if view=='health':rows=[]
            elif reduced:rows=reduced
            elif callable(traffic):
                rows=lambda:self._iter_correlations(traffic(with_identity=cache.get('identity',True)),dns,contexts,age,scope)
            elif kind in ('traffic','correlations'):rows=self._correlations(traffic,dns,contexts,age,scope)
            elif kind=='dns':rows=[d for d in dns if d['timestamp']>=a]
            else:rows=self._load(kind,a,b,scope)
            cache[key]=(dns,rows)
        dns,rows=cache[key]
        streamed=callable(rows)
        projection=cache.get(('aggregate',history.packed(request)))
        if callable(rows) and view=='facts':
            raise QueryError('Fact budget exceeded; narrow the UTC interval or source scope',code='resource-limit')
        source_rows=[] if projection else rows() if callable(rows) else rows
        unknown_device_buckets=0;selected_count=0
        def selected_rows():
            nonlocal unknown_device_buckets,selected_count
            for row in source_rows:
                if kind in ('traffic','correlations'):
                    unknown_device_buckets+=row.get('device') is None
                    if scope.get('device') and row['device']!=scope['device']:continue
                if self._matches(row,request.get('where')) and self._search(row,request.get('search','')):
                    selected_count+=row.get('_weight',1)
                    yield row
        rows=selected_rows()
        if view=='facts':rows=sorted(rows,key=lambda r:(r['timestamp'],r['id']))
        for order in reversed(request.get('order_by',[]) if view=='facts' else []):
            rows.sort(key=lambda r:(r.get(order['field']) is None,r.get(order['field'])),reverse=order['direction']=='desc')
        coverage_cache=cache.setdefault('coverage',{})
        traffic_coverage=self._coverage('traffic',a,b,scope,request.get('where') if kind!='dns' else None,cache=coverage_cache)
        dns_coverage=self._coverage('dns',a,b,scope,request.get('where') if kind=='dns' else None,cache=coverage_cache)
        coverage={'traffic':traffic_coverage,'dns':dns_coverage,'context_event_coverage':'unavailable',
                  'incomplete':traffic_coverage['incomplete'] if kind in ('traffic','correlations') else dns_coverage['incomplete'] if kind=='dns' else not rows}
        if view=='summary':
            projections=[]
            if streamed:
                for q in cache.get('requests',[]):
                    if q['kind'] in ('traffic','correlations') and q['view'] in ('groups','series') and self._aggregate_family(q)==self._aggregate_family(request):
                        item={'query':q,'values':{}}
                        cache[('aggregate',history.packed(q))]=item;projections.append(item)
            def observe(row):
                for item in projections:self._aggregate_row(item['query'],item['values'],row)
            data=self._summary([] if kind=='dns' else rows,list(rows) if kind=='dns' else [d for d in dns if d['timestamp']>=a],a,b,scope,
                observe=observe if projections else None,health_cache=cache.setdefault('health',{}),coverage_cache=coverage_cache)
            for item in projections:item.update(count=selected_count,unknown_device_buckets=unknown_device_buckets)
        elif view=='series':
            step=request.get('bin_seconds',60)*1000000
            aggregates=projection['values'] if projection else {}
            if projection:selected_count=projection['count'];unknown_device_buckets=projection['unknown_device_buckets']
            else:
                for row in rows:self._aggregate_row(request,aggregates,row)
            bins=[]
            for left in range(a//step*step,b,step):
                right=left+step
                selected=aggregates.get(left,{'events':0,'inbound_bytes':0,'outbound_bytes':0,'total_bytes':0})
                inside_left,inside_right=max(a,left),min(b,right)
                if kind=='dns':
                    known=not self._coverage('dns',inside_left,inside_right,scope,request.get('where'),cache=coverage_cache)['incomplete']
                    bins.append({'start':history.utc(left),'end':history.utc(right),
                                 'scope_start':history.utc(inside_left),'scope_end':history.utc(inside_right),
                                 'events':selected['events'],'represented_microseconds':inside_right-inside_left,
                                 'coverage_incomplete':not known})
                    continue
                known=not self._coverage('traffic',inside_left,inside_right,scope,request.get('where'),cache=coverage_cache)['incomplete'] and not (scope.get('device') and unknown_device_buckets)
                totals={field:selected[field] for field in ('inbound_bytes','outbound_bytes','total_bytes')}
                bins.append({'start':history.utc(left),'end':history.utc(right),**totals,
                             'scope_start':history.utc(inside_left),'scope_end':history.utc(inside_right),
                             'represented_microseconds':inside_right-inside_left,'coverage_incomplete':not known,
                             'rate':{'numerator_bytes':totals['total_bytes'],'denominator_microseconds':inside_right-inside_left,'per_second_scale':1000000} if known else None})
            data=({'bins':bins,'unit':'decisions/bin','denominator':'canonical-provider-decisions'} if kind=='dns'
                  else {'bins':bins,'unit':'B/s','sampled_not_instantaneous':True})
        elif view=='facts':
            limit=request.get('limit',100)
            offset=0
            query_hash=history.digest({k:v for k,v in request.items() if k not in ('cursor','anchor_id')})
            anchor_present=None
            if request.get('anchor_id'):
                anchored=next((i for i,r in enumerate(rows) if r['id']==request['anchor_id']),None)
                anchor_present=anchored is not None
                offset=anchored//limit*limit if anchored is not None else 0
            if request.get('cursor'):
                try:
                    cursor=json.loads(base64.b64decode(request['cursor'],altchars=b'-_',validate=True))
                    if set(cursor)!={'revision','query','offset'} or type(cursor['offset']) is not int or not 0<=cursor['offset']<=len(rows):
                        raise ValueError()
                except (ValueError,TypeError,binascii.Error,UnicodeError):
                    raise QueryError('Malformed cursor') from None
                if cursor['revision']!=revision or cursor['query']!=query_hash:
                    raise QueryError('Stale or mismatched cursor; restart the view')
                offset=cursor['offset']
            next_offset=offset+limit
            def page_cursor(at):
                return base64.urlsafe_b64encode(history.packed({'revision':revision,'query':query_hash,'offset':at}).encode()).decode()
            cursor=page_cursor(next_offset) if next_offset<len(rows) else None
            data={'rows':rows[offset:next_offset],'total_count':len(rows),'next_cursor':cursor,
                  'current_cursor':page_cursor(offset) if offset else None,
                  'previous_cursor':page_cursor(max(0,offset-limit)) if offset else None,
                  'page_offset':offset,'anchor_present':anchor_present}
        elif view=='groups':
            fields=request.get('group_by',[])
            groups=projection['values'] if projection else {}
            if projection:selected_count=projection['count'];unknown_device_buckets=projection['unknown_device_buckets']
            else:
                for row in rows:self._aggregate_row(request,groups,row)
            grouped=[{**{k:v for k,v in value.items() if k!='last'},'last_observed_utc':history.utc(value['last'])} for value in groups.values()]
            for order in reversed(request.get('order_by',[])):
                if order['field'] not in fields and order['field'] not in ('inbound_bytes','outbound_bytes','total_bytes','count'):
                    raise QueryError('Grouped ordering requires a group key or byte aggregate')
                grouped.sort(key=lambda g:(g.get(order['field'],g['keys'].get(order['field'])) is None,
                                           g.get(order['field'],g['keys'].get(order['field']))),reverse=order['direction']=='desc')
            data={'groups':grouped}
        else:
            data=self._summary([],[],a,b,scope,health_cache=cache.setdefault('health',{}),coverage_cache=coverage_cache)['source_health']
        if scope.get('device') and unknown_device_buckets:
            traffic_coverage['incomplete']=True
            traffic_coverage['device_binding_unknown_buckets']=unknown_device_buckets
            if kind in ('traffic','correlations'):coverage['incomplete']=True
        if kind in ('context','policy'):coverage['incomplete']=not selected_count
        value_state='unobserved' if coverage['incomplete'] and not selected_count else 'partial' if coverage['incomplete'] else 'observed'
        if view=='summary':
            data['data']['complete_total_bytes']=data['data']['total_bytes'] if not coverage['incomplete'] else None
            data['data']['applicable']=kind in ('traffic','correlations')
            data['dns_activity']['filter_domain']='selected DNS facts' if kind=='dns' else 'independent account/endpoint UTC scope; query DNS separately for DNS-specific predicates'
        return {'revision':revision,'scope':scope,'start':history.utc(a),'end':history.utc(b),'coverage':coverage,
                'value_state':value_state,'max_age_seconds':age,
                'capabilities':{'policy':'stored-snapshot' if kind=='policy' and selected_count else 'not-collected','outcomes':OUTCOME_VERSION,
                                'verified_protocol':'unavailable','destination_geography_asn':'controld-single-answer-metadata'},
                'aggregation_version':VERSION,'correlation_version':CORRELATION_VERSION,'data':data}

    @staticmethod
    def _aggregate_row(request,values,row):
        if request['view']=='series':
            left=row['timestamp']//(request.get('bin_seconds',60)*1000000)*(request.get('bin_seconds',60)*1000000)
            value=values.setdefault(left,{'events':0,'inbound_bytes':0,'outbound_bytes':0,'total_bytes':0})
            value['events']+=row.get('_weight',1)
        else:
            fields=request.get('group_by',[]);key=tuple(row.get(f) for f in fields)
            value=values.get(key)
            if value is None:
                value={'keys':dict(zip(fields,key)),'inbound_bytes':0,'outbound_bytes':0,'total_bytes':0,
                    'count':0,'last':row['timestamp'],'correlation_counts':{state:0 for state in ('unmatched','unique-candidate','ambiguous','unusable')}}
                values[key]=value
            value['count']+=row.get('_weight',1);value['last']=max(value['last'],row['timestamp'])
            if row.get('correlation_state') in value['correlation_counts']:value['correlation_counts'][row['correlation_state']]+=row.get('_weight',1)
        for field in ('inbound_bytes','outbound_bytes','total_bytes'):value[field]+=row.get(field,0)

    @staticmethod
    def _matches(row,where):
        if 'candidates' in row:
            return any(Analytics._evaluate(row,where,candidate) for candidate in row['candidates'] or [None])
        return Analytics._evaluate(row,where)

    @staticmethod
    def _evaluate(row,where,candidate=None):
        if not where:
            return True
        if 'all' in where:
            return all(Analytics._evaluate(row,c,candidate) for c in where['all'])
        if 'any' in where:
            return any(Analytics._evaluate(row,c,candidate) for c in where['any'])
        field,op,value=where['field'],where['op'],where['value']
        if field in DNS_FIELDS and field not in row:
            if candidate is None: return False
            observed=candidate.get(field)
        else:
            observed=row.get(field)
        if op=='eq': return observed==value
        if op=='ne': return observed!=value
        if op=='in': return observed in value
        if op=='contains': return observed is not None and value is not None and value.casefold() in observed.casefold()
        if observed is None or value is None: return False
        if op=='gt': return observed>value
        if op=='gte': return observed>=value
        if op=='lt': return observed<value
        return observed<=value

    @staticmethod
    def _search(row,text):
        if not text: return True
        values=[row.get(f) for f in ('application_path','destination_ip','question','endpoint','reason','node_id','resolver_endpoint')]
        values.extend(c['question'] for c in row.get('candidates',[]))
        return any(text.casefold() in v.casefold() for v in values if isinstance(v,str))

    @staticmethod
    def _totals(rows):
        incoming=sum(r.get('inbound_bytes',0) for r in rows)
        outgoing=sum(r.get('outbound_bytes',0) for r in rows)
        return {'inbound_bytes':incoming,'outbound_bytes':outgoing,'total_bytes':incoming+outgoing}

    def _summary(self,rows,dns,a,b,scope,*,observe=None,health_cache=None,coverage_cache=None):
        def counter():return {'bucket_count':0,'inbound_bytes':0,'outbound_bytes':0,'total_bytes':0}
        def add(value,row):
            value['bucket_count']+=row.get('_weight',1)
            for field in ('inbound_bytes','outbound_bytes','total_bytes'):value[field]+=row.get(field,0)
        classes={state:counter() for state in ('unmatched','unique-candidate','ambiguous','unusable')}
        rankings={field:defaultdict(counter) for field in ('application','destination_ip','destination_country','destination_asn')}
        inferred=defaultdict(counter);total=counter();applications=set();unknown_applications=0
        for row in rows:
            if observe:observe(row)
            add(total,row)
            if row.get('application'):applications.add(row['application'])
            else:unknown_applications+=row.get('_weight',1)
            if row.get('correlation_state') in classes:add(classes[row['correlation_state']],row)
            for field,values in rankings.items():add(values[row.get(field)],row)
            if row.get('correlation_state')=='unique-candidate':add(inferred[row['candidates'][0]['question']],row)
        def ranking(field):
            return sorted([{'value':key,**value} for key,value in rankings[field].items()],
                          key=lambda r:(-r['total_bytes'],str(r['value'])))
        dns_groups={}
        for field in ('endpoint','profile','question','type','action','reason','protocol','client'):
            groups=defaultdict(int)
            for row in dns: groups[row.get(field)]+=1
            dns_groups[field]=[{'value':key,'events':count} for key,count in sorted(groups.items(),key=lambda x:(-x[1],str(x[0])))]
        health_cache={} if health_cache is None else health_cache
        health_key=(a,b,history.packed(scope))
        cached_health=health_key in health_cache
        health=health_cache.get(health_key,[])
        # The measured bottleneck was three repeated Python decodes of the
        # entire traffic horizon per summary. Count each source in one SQL pass.
        unsupported={} if cached_health else dict(self.store.db.execute(
            "SELECT source,count(*) FROM traffic WHERE time>=? AND time<? "
            "AND json_extract(data,'$.destination_status')='unsupported-address-family' GROUP BY source",(a,b)))
        for item in ([] if cached_health else self.store.health()['sources']):
            meta=self.store.db.execute('SELECT metadata FROM sources WHERE id=?',(item['id'],)).fetchone()
            metadata=json.loads(meta[0])
            field='host' if item['kind']=='traffic' else 'account'
            if scope.get(field) and metadata['scope']!=scope[field]: continue
            if item['kind']=='dns' and scope.get('endpoint') and metadata.get('endpoint')!=scope['endpoint']: continue
            runs=self.store.db.execute('SELECT * FROM runs WHERE source=? AND end>? AND start<? ORDER BY revision',(item['id'],a,b)).fetchall()
            last=self.store.db.execute("SELECT max(collected) FROM runs WHERE source=? AND state='complete'",(item['id'],)).fetchone()[0]
            requested=self.store.db.execute('SELECT max(end) FROM runs WHERE source=?',(item['id'],)).fetchone()[0]
            health.append({**item,'last_successful_read':history.utc(last) if last else None,
                'requested_through':history.utc(requested) if requested else None,
                'lag_microseconds':max(0,self.store.now-history.instant(item['complete_through'])) if item['complete_through'] else None,
                'lag_domain':'as-of-now minus complete-through, not network activity',
                'requested_lag_microseconds':max(0,requested-history.instant(item['complete_through'])) if requested and item['complete_through'] else None,
                'attempt_states':[r['state'] for r in runs],
                'coverage':self.store._coverage(item['kind'],a,b,item['id'],cache=coverage_cache),
                'age_since_last_success_microseconds':max(0,self.store.now-last) if last else None,
                'as_of_utc':history.utc(self.store.now),
                'unsupported_rows':unsupported.get(item['id'],0) if item['kind']=='traffic' else
                                   sum(unsupported_answer(json.loads(r['data'])['raw'])
                                       for r in self.store.db.execute('SELECT data FROM dns INDEXED BY dns_time WHERE source=? AND time>=? AND time<?',(item['id'],a,b))),
                'unsupported_rows_definition':'unsupported-address-family' if item['kind']=='traffic' else 'unsupported-answer-encoding'})
        health_cache[health_key]=health
        geography={field:defaultdict(int) for field in ('provider_country','provider_asn')}
        for decision in dns:
            for field,counts in geography.items():counts[decision[field]]+=1
        counts={name:0 for name in ('allow','block','redirect','failed','other','unknown')}
        for decision in dns:counts[decision['outcome']]+=1
        denominator=sum(counts[name] for name in ('allow','block','redirect','other'))
        return {'data':{**{k:v for k,v in total.items() if k!='bucket_count'},'unit':'bytes','denominator':'canonical-traffic-buckets'},
            'application_activity':{'known_distinct':len(applications),
                                    'unknown_buckets':unknown_applications,'bucket_count':total['bucket_count']},
            'top_applications':ranking('application'),'top_destinations':ranking('destination_ip'),
            'dns_activity':{'events':len(dns),'groups':dns_groups,'denominator':'canonical-provider-decisions'},
            'dns_outcomes':{'counts':counts,'classified_denominator':denominator,'excluded_unknown':counts['unknown'],
                            'excluded_failed':counts['failed'],'block_rate':counts['block']/denominator if denominator else None,
                            'capability':OUTCOME_VERSION,'mapping_source':'https://docs.controld.com/docs/log-field-reference'},
            'dns_questions':{'distinct':len({d['question'] for d in dns}),'ranking':dns_groups['question'],'normalization_version':'raw-spelling-v1'},
            'correlation_coverage':classes,
            'candidate_domains':{'label':'inferred-not-exact-domain-usage',
                'inferred':[{'question':q,**{k:v for k,v in value.items() if k!='bucket_count'}} for q,value in sorted(inferred.items())],
                'ambiguous_bytes':classes['ambiguous']['total_bytes'],
                'unmatched_bytes':classes['unmatched']['total_bytes'],'unusable_bytes':classes['unusable']['total_bytes']},
            'geography_asn':{'capability':'controld-single-answer-metadata',
                'source':'Control D answerCountryCode/answerASN; unique temporal candidate, inferred',
                'countries':ranking('destination_country'),'asns':ranking('destination_asn'),
                'unknown_bytes':rankings['destination_country'].get(None,{}).get('total_bytes',0),
                'unknown_asn_bytes':rankings['destination_asn'].get(None,{}).get('total_bytes',0),
                'provider_decisions':{'country':[{'value':v,'events':n} for v,n in sorted(geography['provider_country'].items(),key=lambda x:str(x[0]))],
                    'asn':[{'value':v,'events':n} for v,n in sorted(geography['provider_asn'].items(),key=lambda x:str(x[0]))]},
                'source_country_is_not_destination_country':True},
            'source_health':{'sources':health,'domain':'operational-not-network-activity'}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history',required=True)
    commands=parser.add_subparsers(dest='command',required=True)
    query=commands.add_parser('query',help='Bounded typed batch; private JSON export')
    query.add_argument('--request-stdin',required=True,action='store_true')
    query.add_argument('--output',required=True)
    capture=commands.add_parser('capture-context',help='One point observation; no historic backfill')
    capture.add_argument('--scope',required=True)
    capture.add_argument('--tailscale-cli',default='C:/Program Files/Tailscale/tailscale.exe')
    delete=commands.add_parser('delete-snapshots')
    delete.add_argument('--kind',choices=['context','policy'],required=True)
    delete.add_argument('--scope',required=True)
    delete.add_argument('--start',required=True)
    delete.add_argument('--end',required=True)
    args=parser.parse_args(argv)
    store=None
    try:
        store=history.History(args.history)
        engine=Analytics(store)
        if args.command=='query':
            wire=sys.stdin.read(1024*1024+1)
            if len(wire)>1024*1024: raise QueryError('Query request size budget exceeded')
            requests=json.loads(wire)
            data=engine.batch(requests)
            path=Path(args.output).resolve()
            if path.parent!=store.directory or path.is_symlink():
                raise QueryError('Query export must be a new file in the private history directory')
            controld.export_private(path,ingestion.exact_json(data))
            print(json.dumps({'revision':data['revision'],'result_count':len(data['results']),
                              'coverage_incomplete':any(r['coverage']['incomplete'] for r in data['results'])}))
        elif args.command=='capture-context':
            engine.record_context(args.scope,capture_context(args.tailscale_cli))
            print(json.dumps({'captured':True,'observation':'point-only','historical_backfill':False}))
        else:
            engine.delete_snapshots(args.kind,args.start,args.end,scope=args.scope)
            print(json.dumps({'deleted':True,'replay_suppression':True}))
        return 0
    except (QueryError,history.HistoryError,controld.ControlDError) as error:
        print(str(error),file=sys.stderr)
        return 1
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error):
        print('Analytics operation failed; verify typed input and private history',file=sys.stderr)
        return 1
    finally:
        if store is not None: store.close()


if __name__=='__main__':
    raise SystemExit(main())
