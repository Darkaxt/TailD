"""Owned elevated source/pipe acceptance. DNS lookups only; no policy changes."""
import argparse
import json
import os
from pathlib import Path
import socket
import threading
import uuid

import analytics
import app_dns
import history
import reader


def run(output,cli):
    output.mkdir(parents=True,exist_ok=False)
    sid=reader.current_sid();reader.drop_unused_privileges()
    source=reader.GlassWireSource(owner_sid=sid)
    server=reader.PipeServer('dns-acceptance-'+uuid.uuid4().hex,sid,source)
    errors=[]
    def serve():
        try:server.serve()
        except BaseException as error:errors.append(type(error).__name__)
    worker=threading.Thread(target=serve);worker.start();server.ready.wait()
    client=reader.PipeClient(server.name.rsplit('.',1)[-1])
    events=[];session=None;after=0
    names=['example.com','googleads.g.doubleclick.net','taild-probe-'+uuid.uuid4().hex+'.invalid']
    try:
        first=client.request({'op':'app-dns','enabled':True,'session':None,'after':0})
        session=first['session'];after=first['sequence']
        assert first['state']=='observing',first['state']
        for name in names:
            try:socket.getaddrinfo(name,443)
            except socket.gaierror:pass
        context=analytics.capture_context(cli)
        binding={'endpoint':context.get('resolver_endpoint'),'at':context['captured_at_utc'],
                 'method':'active-resolver-point-observation-after-batch'}
        while True:
            final=client.request({'op':'app-dns','enabled':False,'session':session,'after':after})
            if not final.get('events'):break
            events.extend({**e,'binding':binding} for e in final['events'] if e['process']['pid']==os.getpid() and e['question'] in names)
            after=final['sequence']
        assert source.dns_trace is None,'Stopped batches were not acknowledged'
        assert any(e['question']=='example.com' and e['status']==0 for e in events),events
        assert any(e['question'].endswith('.invalid') and e['status']!=0 for e in events),events
        with_store=history.History(output/'history',now=context['captured_at_utc'])
        try:
            app_dns.import_batch(with_store,{'session':session,'events':events},'local-windows')
            assert with_store.db.execute("SELECT count(*) FROM snapshots WHERE kind='app-dns'").fetchone()[0]==len(events)
        finally:with_store.close()
        result={'ok':True,'private_trace_stopped':True,'final_batch_acknowledged':True,
                'reduced_privileges':True,'events':events,'session':session,'global_dns_log_changed':False,
                'resolver_endpoint':context.get('resolver_endpoint'),'lost':final.get('lost',0)}
        (output/'source-acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:result[k] for k in ('ok','private_trace_stopped','final_batch_acknowledged','reduced_privileges')}))
    finally:
        client.close();server.stop();worker.join();source.after_disconnect()
    assert not errors,errors


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--cli',required=True,type=Path)
    args=parser.parse_args();run(args.output,args.cli)
