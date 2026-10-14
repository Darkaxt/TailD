"""On-demand Stage 4 ingest/query/delete commands. No background installation."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

import controld
import glasswire
import history


def dns_windows(store, scope, endpoint, start, end, fetch, *, max_slices=1024, checkpoint=None,
                defer_budget=False, resume_pending=None, progress=None, commit=None):
    """Deterministic UTC subdivision; a capped one-second slice stays incomplete.

    fetch is the existing GET-only boundary in the CLI. Each returned slice owns
    its entire multiset, not an append offset. No provider call holds a store tx.
    """
    a, b = history.bounds(start, end)
    commit = commit or (lambda action: action())
    original_a = a
    floor = commit(lambda: store.db.execute('SELECT expiry_floor FROM settings').fetchone()[0])
    if a < floor:
        commit(lambda: store.record_gap('dns',scope,history.utc(a),history.utc(min(b,floor)),
                         'source-expired',endpoint=endpoint))
        a = min(b,floor)
    if resume_pending is None:
        pending = [(a,b)] if a<b else []
    else:
        if not defer_budget or not isinstance(resume_pending,list) or len(resume_pending)>1024:
            raise history.HistoryError('Invalid bounded DNS continuation')
        pending = []
        for interval in resume_pending:
            if not isinstance(interval,list) or len(interval)!=2:
                raise history.HistoryError('Invalid bounded DNS continuation')
            x,y = history.bounds(*interval)
            if x<original_a or y>b:
                raise history.HistoryError('DNS continuation leaves its captured root window')
            if max(x,a)<y:
                pending.append((max(x,a),y))
    attempts = 0
    def finish(interrupted=False):
        value = {'slices_read':attempts}
        if defer_budget:
            value['pending_windows'] = [[history.utc(x),history.utc(y)] for x,y in pending]
        if interrupted:
            value['interrupted'] = True
        return value
    while pending:
        if checkpoint is not None and not checkpoint():
            return finish(True)
        if defer_budget and attempts >= max_slices:
            break  # Scheduling budget is not a claim of an irreducible source cap.
        x,y = pending.pop()
        left,right = history.utc(x),history.utc(y)
        if attempts >= max_slices:
            commit(lambda: store.record_gap('dns',scope,left,right,'irreducibly-capped',endpoint=endpoint))
            continue
        attempts += 1
        if progress is not None:progress('reading',left,right)
        try:
            data = fetch(left,right)
        except controld.ControlDError:
            commit(lambda: store.record_gap('dns',scope,left,right,'read-failed',endpoint=endpoint))
            raise
        if data['query_window']['start_inclusive'] != left or history.instant(data['query_window'].get('end_exclusive') or data['query_window']['end_inclusive']) != y:
            raise history.HistoryError('Provider returned mismatched query bounds')
        result = commit(lambda: store.import_dns(data,scope,endpoint))
        if progress is not None:progress('committed',left,right)
        if result['state'] == 'truncated':
            midpoint = ((x+y)//2000000)*1000000
            if x < midpoint < y and y-x > 1000000:
                pending.extend([(midpoint,y),(x,midpoint)])
            else:
                commit(lambda: store.record_gap('dns',scope,left,right,'irreducibly-capped',endpoint=endpoint))
    return finish()


def traffic_window(store, scope, start, end, directory=None, limit=10000, *, reader=None,
                   checkpoint=None, progress=None, commit=None, max_slices=1024,
                   defer_budget=False, resume_pending=None):
    """Recent-first slices with replay-safe, bounded retained-history continuation.

    Acquisition runs outside the writer. Only commit callbacks access its store;
    the default remains synchronous for explicit on-demand ingestion commands.
    """
    commit = commit or (lambda action: action())
    if checkpoint is not None and not checkpoint():
        result={'slice_attempts':0,'interrupted':True}
        if defer_budget:result['pending_windows']=resume_pending
        return result  # No catalog read after pause/stop has been admitted.
    source = reader or glasswire
    catalog = source.discover(directory)
    results = []
    a,b = history.bounds(start,end)
    floor = commit(lambda: store.db.execute('SELECT expiry_floor FROM settings').fetchone()[0])
    if a < floor:
        commit(lambda: store.record_gap('traffic',scope,start,history.utc(min(b,floor)),
                         'source-expired',generation={'catalog':catalog['directory']}))
        a = min(b,floor)
    present=[entry for entry in catalog['databases'] if entry['present']]
    if present:
        earliest=min(entry['timestamp'] for entry in present)*1000000
        if a<min(b,earliest):
            commit(lambda: store.record_gap('traffic',scope,history.utc(a),history.utc(min(b,earliest)),
                             'source-expired',generation={'catalog':catalog['directory']}))
    entries={str(entry['path']):entry for entry in present}
    for index,entry in enumerate(catalog['databases']):
        if not entry['present']:
            left=max(a,entry['timestamp']*1000000)
            right=min(b,catalog['databases'][index+1]['timestamp']*1000000) if index+1<len(catalog['databases']) else b
            if left<right:
                commit(lambda: store.record_gap('traffic',scope,history.utc(left),history.utc(right),'source-expired',
                                 generation={'missing_catalog_path': entry['path']}))
    if resume_pending is None:
        # Stack pop visits newest catalog/day first. Do not assume older mutable
        # history is final: completed horizons are reconciled again in later passes.
        intervals=[(x,min(b,x+86400*1000000)) for x in range(a,b,86400*1000000)] if reader is not None else ([(a,b)] if a<b else [])
        pending=[{'path':str(entry['path']),'start':history.utc(x),'end':history.utc(y)}
                 for entry in present for x,y in intervals]
    else:
        if not defer_budget or not isinstance(resume_pending,list) or len(resume_pending)>32768:
            raise history.HistoryError('Invalid bounded traffic continuation')
        pending=[]
        for item in resume_pending:
            if not isinstance(item,dict) or set(item)!={'path','start','end'} or not isinstance(item['path'],str):
                raise history.HistoryError('Invalid bounded traffic continuation')
            x,y=history.bounds(item['start'],item['end'])
            if x<history.instant(start) or y>b or reader is not None and y-x>86400*1000000:
                raise history.HistoryError('Traffic continuation leaves its captured root window')
            if max(a,x)<y:pending.append({**item,'start':history.utc(max(a,x))})
    def finish(interrupted=False):
        result={'slice_attempts':len(results),'truncated_attempts':sum(r['state']=='truncated' for r in results)}
        if defer_budget:result['pending_windows']=pending
        if interrupted:result['interrupted']=True
        return result
    attempts={}
    while pending:
        if checkpoint is not None and not checkpoint():return finish(True)
        if defer_budget and len(results)>=max_slices:break
        item=pending.pop();left,right=item['start'],item['end'];x,y=history.bounds(left,right)
        entry=entries.get(item['path'])
        if entry is None:
            commit(lambda: store.record_gap('traffic',scope,left,right,'source-expired',
                generation={'missing_catalog_path':item['path']}))
            continue
        generation = {'traffic_database':source.physical_identity(entry['path']),
                      'application_database':source.physical_identity(catalog['main_database'])}
        if not defer_budget and attempts.get(item['path'],0)>=max_slices:
            commit(lambda: store.record_gap('traffic',scope,left,right,'irreducibly-capped',generation=generation))
            continue
        attempts[item['path']]=attempts.get(item['path'],0)+1
        if progress is not None:progress('reading',left,right)
        try:
            data = source.read_traffic(entry['path'],catalog['main_database'],left,right,limit)
            data['source_version'] = catalog['version'];data['catalog_record'] = entry
            generation = data['generation']
            result = commit(lambda: store.import_traffic(data,scope))
            if progress is not None:progress('committed',left,right)
            results.append(result)
            if result['state'] == 'truncated':
                midpoint = ((x+y)//2000000)*1000000
                if x < midpoint < y and y-x>1000000:
                    pending.extend([{**item,'end':history.utc(midpoint)},
                                    {**item,'start':history.utc(midpoint)}])
                else:
                    commit(lambda: store.record_gap('traffic',scope,left,right,'irreducibly-capped',generation=generation))
        except glasswire.GlassWireError:
            commit(lambda: store.record_gap('traffic',scope,left,right,'read-failed',generation=generation))
            raise
    if not catalog['databases']:
        commit(lambda: store.record_gap('traffic',scope,start,end,'source-expired',generation={'catalog':catalog['directory']}))
    return finish()


def exact_json(value):
    """Byte counters cross JSON boundaries as decimal strings, not JS doubles."""
    if isinstance(value, dict):
        return {k: str(v) if k.endswith('_bytes') and type(v) is int else exact_json(v) for k,v in value.items()}
    if isinstance(value,list):
        return [exact_json(v) for v in value]
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history',required=True,help='Owned private directory outside the repository')
    parser.add_argument('--retention-days',type=int,help='Explicit retention setting; default seven days')
    commands = parser.add_subparsers(dest='command',required=True)
    traffic = commands.add_parser('glasswire')
    traffic.add_argument('--directory',help='Validated source-directory override')
    traffic.add_argument('--scope',required=True,help='Explicit host scope, not a guessed endpoint binding')
    traffic.add_argument('--limit',type=int,default=10000)
    dns = commands.add_parser('controld')
    dns.add_argument('--scope',required=True,help='Explicit account scope')
    dns.add_argument('--endpoint',required=True)
    dns.add_argument('--account-type',choices=['personal','organization'],required=True)
    dns.add_argument('--instance',required=True)
    dns.add_argument('--organization')
    dns.add_argument('--limit',type=int,default=1000)
    dns.add_argument('--token-stdin',action='store_true',required=True)
    saved = commands.add_parser('import-dns')
    saved.add_argument('--input',required=True,help='Previously authorized private bounded slice')
    saved.add_argument('--scope',required=True)
    saved.add_argument('--endpoint',required=True)
    query = commands.add_parser('query')
    query.add_argument('--kind',choices=['traffic','dns'],required=True)
    query.add_argument('--source')
    query.add_argument('--application-path')
    query.add_argument('--endpoint')
    query.add_argument('--question')
    query.add_argument('--destination-ip')
    query.add_argument('--destination-port',type=int)
    query.add_argument('--limit',type=int,default=1000)
    query.add_argument('--output',required=True,help='New JSON inside this private history directory')
    delete = commands.add_parser('delete')
    delete.add_argument('--kind',choices=['traffic','dns'],required=True)
    delete.add_argument('--source')
    delete.add_argument('--application-path')
    commands.add_parser('health')
    commands.add_parser('cleanup')
    for command in (traffic,dns):
        selection = command.add_mutually_exclusive_group(required=True)
        selection.add_argument('--start')
        selection.add_argument('--resume',action='store_true',help='Reconcile the retained history horizon; no unproven finalization cutoff')
    for command in (query,delete):
        command.add_argument('--start',required=True)
    for command in (traffic,dns,query,delete):
        command.add_argument('--end',required=True)
    args = parser.parse_args(argv)
    store = None
    try:
        store = history.History(args.history,retention_days=args.retention_days)
        if getattr(args,'resume',False):
            args.start = store.health()['expiry_floor']
        if args.command == 'glasswire':
            summary = traffic_window(store,args.scope,args.start,args.end,args.directory,args.limit)
        elif args.command == 'controld':
            token = sys.stdin.readline().strip()
            def fetch(start,end):
                return controld.activity_slice(token,args.account_type,args.instance,start,end,
                    endpoint=args.endpoint,organization=args.organization,limit=args.limit)
            summary = dns_windows(store,args.scope,args.endpoint,args.start,args.end,fetch)
        elif args.command == 'import-dns':
            path = Path(args.input).resolve(strict=True)
            if path.is_relative_to(Path(__file__).resolve().parents[2]):
                raise history.HistoryError('Private source inputs must be outside the repository')
            data = json.loads(path.read_text(encoding='utf-8'))
            result = store.import_dns(data,args.scope,args.endpoint)
            summary = {'revision':result['revision'],'state':result['state']}
        elif args.command == 'query':
            filters = {key:getattr(args,key) for key in ('source','application_path','endpoint','question','destination_ip','destination_port') if getattr(args,key) is not None}
            data = store.query(args.kind,args.start,args.end,limit=args.limit,**filters)
            path = Path(args.output).resolve()
            if path.parent != store.directory or path.is_symlink():
                raise history.HistoryError('Query export must be a new file in the private history directory')
            controld.export_private(path,exact_json(data))
            summary = {k:data[k] for k in ('revision','row_count','truncated')}
            summary['coverage_incomplete'] = data['coverage']['incomplete']
        elif args.command == 'delete':
            store.delete(args.kind,args.start,args.end,source=args.source,application_path=args.application_path)
            summary = {'deleted':True,'replay_suppression':True}
        else:
            if args.command == 'cleanup':
                store.cleanup()
            summary = store.health()
        print(json.dumps(summary))
        return 0
    except (history.HistoryError,glasswire.GlassWireError,controld.ControlDError) as error:
        print(str(error),file=sys.stderr)
        return 1
    except (sqlite3.Error,OSError,ValueError,KeyError,TypeError):
        print('History operation failed; verify private inputs and source compatibility',file=sys.stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
