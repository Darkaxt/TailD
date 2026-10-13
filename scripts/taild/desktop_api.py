"""Fixed desktop operations over the owning collector's existing private store.

No paths, SQL, credentials, network access or privileged operations from renderer.
Exports are revision-bound content; only the native owner dialog chooses a path.
"""
import copy
import csv
import io
import json
import os
import re

import analytics
import history
import ingestion


OPERATIONS = frozenset(('view-query','view-catalog','saved-query','export-query','retention','delete-snapshots'))


class DesktopAPI:
    def __init__(self,store):
        self.store=store
        self.engine=analytics.Analytics(store)

    def query(self,value):
        value=copy.deepcopy(value)
        if not isinstance(value,dict):
            raise analytics.QueryError('Expected typed query')
        fields=self.engine._fields(value.get('kind'))
        def predicate(node):
            if not isinstance(node,dict): return
            if set(node) in ({'all'},{'any'}):
                children=next(iter(node.values()))
                if isinstance(children,list):
                    for child in children: predicate(child)
            elif fields.get(node.get('field')) is int:
                values=node.get('value') if node.get('op')=='in' else [node.get('value')]
                if not isinstance(values,list): return
                converted=[]
                for item in values:
                    if isinstance(item,str):
                        if not re.fullmatch(r'-?[0-9]{1,20}',item):
                            raise analytics.QueryError('Expected decimal integer filter')
                        item=int(item)
                    converted.append(item)
                node['value']=converted if node.get('op')=='in' else converted[0]
        predicate(value.get('where'))
        self.engine._validate(value)
        return value

    def dispatch(self,op,body):
        if not isinstance(body,dict): raise analytics.QueryError('Expected typed operation')
        if op=='view-query' and set(body)<={'queries','revision'} and 'queries' in body:
            if not isinstance(body['queries'],list) or not 1<=len(body['queries'])<=16:
                raise analytics.QueryError('Expected bounded query batch')
            queries=[self.query(q) for q in body['queries']]
            return ingestion.exact_json(self.engine.batch(queries,expected_revision=body.get('revision')))
        if op=='view-catalog' and not body:
            sources=[{'id':r['id'],'kind':r['kind'],**{k:v for k,v in json.loads(r['metadata']).items()
                     if k in ('scope','endpoint')}} for r in self.store.db.execute('SELECT * FROM sources ORDER BY kind,id')]
            intervals={kind:{'start':history.utc(row[0]) if row[0] is not None else None,
                             'latest_observation':history.utc(row[1]) if row[1] is not None else None,
                             'end':history.utc(row[1]+(1000000 if kind=='traffic' else 1)) if row[1] is not None else None}
                       for kind,table in (('traffic','traffic'),('dns','dns'),('snapshots','snapshots'))
                       for row in [self.store.db.execute('SELECT min(time),max(time) FROM '+table).fetchone()]}
            nodes=[{'host_scope':r[0],'node_id':r[1]} for r in self.store.db.execute(
                "SELECT DISTINCT scope,json_extract(data,'$.node_id') FROM snapshots WHERE kind='context' AND json_extract(data,'$.node_id') IS NOT NULL LIMIT 513")]
            return ingestion.exact_json({'sources':sources,'intervals':intervals,'health':self.store.health(),
                                         'nodes':nodes[:512],'nodes_truncated':len(nodes)>512})
        if op=='saved-query': return self.saved(body)
        if op=='export-query' and set(body)=={'query','revision','format'}:
            if body['format'] not in ('json','csv') or type(body['revision']) is not int:
                raise analytics.QueryError('Unsupported export')
            original=body['query']
            request=self.query(original)
            if request['view']!='facts' or request.get('cursor') or request.get('anchor_id'):
                raise analytics.QueryError('Export requires whole scoped facts, not a page')
            request['limit']=10000
            batch=self.engine.batch([request],expected_revision=body['revision'])
            result=ingestion.exact_json(batch['results'][0])
            if result['data']['next_cursor']:
                raise analytics.QueryError('Narrow export scope to 10000 facts',code='resource-limit')
            envelope={'schema':'taild-desktop-evidence-v1','schema_version':self.store.health()['schema_version'],
                      'aggregation_version':batch['aggregation_version'],'correlation_version':batch['correlation_version'],
                      'revision':batch['revision'],'query':original,'unit':'bytes','result':result}
            if body['format']=='json':
                content=json.dumps(envelope,ensure_ascii=False,allow_nan=False,indent=2)
            else:
                # Fixed columns, no provider-defined CSV headers or lossy doubles.
                fields=['row_type','schema','aggregation_version','correlation_version','revision','scope','start','end',
                        'unit','value_state','coverage','id','timestamp','source','application','application_path',
                        'destination_ip','destination_port','protocol_raw','inbound_bytes','outbound_bytes','total_bytes',
                        'endpoint','profile','question','type','action','outcome','reason','correlation_state','context_state','evidence']
                stream=io.StringIO(newline='')
                writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\r\n')
                writer.writeheader()
                meta={k:envelope[k] for k in ('schema','aggregation_version','correlation_version','revision','unit')}
                meta.update({k:result[k] for k in ('scope','start','end','value_state','coverage')})
                def safe(value):
                    if isinstance(value,(dict,list)): value=json.dumps(value,ensure_ascii=False,separators=(',',':'))
                    if value is None: return ''
                    text=str(value)
                    return "'"+text if text.lstrip('\t\r\n ').startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text
                for row in result['data']['rows'] or [None]:
                    values={**meta,'row_type':'fact' if row is not None else 'scope-metadata'}
                    if row is not None:
                        values.update({k:row.get(k) for k in fields if k in row and k not in meta})
                        values['evidence']=row
                    writer.writerow({k:safe(v) for k,v in values.items()})
                content=stream.getvalue()
            if len(content.encode('utf-8'))>6*1024*1024:
                raise analytics.QueryError('Export content bound exceeded',code='resource-limit')
            return {'content':content,'format':body['format'],'revision':batch['revision'],
                    'row_count':result['data']['total_count'],'formula_safe':body['format']=='csv',
                    'coverage_incomplete':result['coverage']['incomplete'],'unit':'bytes'}
        if op=='retention' and set(body)=={'days'} and type(body['days']) is int and 1<=body['days']<=3650:
            with self.store.transaction():
                self.store.db.execute('UPDATE settings SET retention_days=?',(body['days'],))
                self.store._expire()
            return ingestion.exact_json(self.store.health())
        if op=='delete-snapshots' and set(body)=={'kind','start','end'} and body['kind'] in ('context','policy'):
            a,b=history.bounds(body['start'],body['end'])
            with self.store.transaction():
                self.store._bump()
                self.store.db.execute('INSERT INTO suppressions VALUES(?,NULL,?,?,NULL)',(body['kind'],a,b))
                self.store.db.execute('DELETE FROM snapshots WHERE kind=? AND end>? AND time<?',(body['kind'],a,b))
            return {'deleted':True,'replay_suppression':True,'external_sources_changed':False}
        raise analytics.QueryError('Unsupported desktop operation')

    def saved(self,body):
        target=self.store.directory/'desktop-queries.json'
        pending=self.store.directory/'desktop-queries.pending.json'
        for path in (target,pending):
            if path.exists() and (path.is_symlink() or path.stat().st_nlink!=1 or path.stat().st_size>65536):
                raise analytics.QueryError('Invalid private saved-query file')
        try:
            values=json.loads(target.read_text(encoding='utf-8')) if target.exists() else []
        except (ValueError,UnicodeError):
            raise analytics.QueryError('Malformed saved query catalog; existing file preserved') from None
        if not isinstance(values,list) or len(values)>32:
            raise analytics.QueryError('Invalid saved query catalog')
        for value in values:
            if not isinstance(value,dict) or set(value)!={'name','query'} or not isinstance(value['name'],str):
                raise analytics.QueryError('Invalid saved query entry')
            self.query(value['query'])
        if body=={'action':'list'}: return {'queries':values}
        if body.get('action') not in ('save','remove') or set(body) != ({'action','name','query'} if body['action']=='save' else {'action','name'}):
            raise analytics.QueryError('Unsupported saved query operation')
        name=body['name']
        if not isinstance(name,str) or not name.strip() or len(name)>80 or any(ord(c)<32 for c in name):
            raise analytics.QueryError('Expected bounded saved query name')
        values=[v for v in values if v['name']!=name]
        if body['action']=='save':
            self.query(body['query'])
            if body['query'].get('cursor') or body['query'].get('anchor_id'): raise analytics.QueryError('Cannot save transient page cursor/anchor')
            values.append({'name':name,'query':body['query']})
        if len(values)>32 or len(history.packed(values).encode())>65536:
            raise analytics.QueryError('Saved query bound exceeded',code='resource-limit')
        with pending.open('w',encoding='utf-8',newline='') as output:
            json.dump(values,output,ensure_ascii=False)
            output.flush();os.fsync(output.fileno())
        pending.replace(target)
        return {'queries':values}
