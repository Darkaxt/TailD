"""Explicit real-provider acceptance. Test writes only in a newly created profile."""
import argparse
from contextlib import closing
from datetime import datetime,timezone
import json
from pathlib import Path
import secrets
import sys
import threading
from urllib.parse import urlencode
from urllib.request import Request,build_opener
from unittest.mock import patch

import analytics
import controld
import credentials
import history
import live_dns
import management


def fixture_request(token,method,path,payload=None):
    with build_opener(controld.NoRedirect).open(Request(controld.API_BASE+path,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/x-www-form-urlencoded'},
        data=urlencode(payload or {}).encode(),method=method)) as response:
        value=json.load(response)
    if value.get('success') is not True:raise ValueError('Fixture operation rejected')
    return value.get('body',{})


def validate_writes(read,write,endpoint,provider):
    before=controld.policy_snapshot(read,endpoint,account_scope=provider['account_scope'])
    before_hash=management.fingerprint(before)
    name='TailD acceptance '+secrets.token_hex(5)
    fixture_request(write,'POST','/profiles',{'name':name})
    matches=[p for p in controld.inventory(read)['profiles'] if p.get('name')==name]
    if len(matches)!=1:raise ValueError('Created fixture identity cannot be established')
    profile=controld._identifier(matches[0]['PK'])
    operations=[]
    try:
        def snapshot(*args):
            resources={'endpoints':{'state':'available','data':{'devices':[]}}}
            for key,suffix in (('rules','rules/all'),('filters','filters'),('services','services'),('options','options')):
                resources[key]={'state':'available','data':controld._body('/profiles/'+profile+'/'+suffix,read)}
            return management.option_catalog({'endpoint':'unassigned-acceptance-fixture','profile':profile,'resources':resources},read)
        manager=management.Management()
        # This unassigned profile intentionally has no fake provider device. The
        # actual production association is independently read/verified above.
        with patch.object(manager,'_read',side_effect=snapshot):
            def action(change):
                preview=manager.dispatch('management-prepare',{'endpoint':'unassigned-acceptance-fixture','change':change},provider)
                result=manager.dispatch('management-apply',{'ticket':preview['ticket'],'confirm':True},provider)
                if result['state']!='applied' or not result['readback']:raise ValueError('Readback failed')
                operations.append(change['kind']+('-delete' if change.get('delete') else '-'+str(change.get('do',change.get('status')))))
            action({'kind':'rule','hostname':'taild-acceptance.invalid','do':0,'status':1,'comment':'Temporary acceptance'})
            action({'kind':'rule','hostname':'taild-acceptance.invalid','do':1,'status':1,'comment':'Temporary acceptance'})
            action({'kind':'rule','hostname':'taild-acceptance.invalid','delete':True})
            current=snapshot()
            filters=management.records(current,'filters');services=management.records(current,'services');options=management.records(current,'options')
            if not filters or not options:raise ValueError('Fixture catalogs unavailable')
            f=filters[0];key=f.get('levels',[{}])[0].get('name',f['PK'])
            action({'kind':'filter','id':key,'status':1})
            action({'kind':'filter','id':key,'status':0})
            if not services:
                available=management.records(before,'services')
                if not available:raise ValueError('No provider-returned service for fixture seeding')
                management.write(write,'PUT','/profiles/'+profile+'/services/'+available[0]['PK'],{'do':0,'status':0})
                services=management.records(snapshot(),'services')
            action({'kind':'service','id':services[0]['PK'],'do':0,'status':1})
            action({'kind':'service','id':services[0]['PK'],'do':1,'status':1})
            option=next(o for o in options if o['PK']=='block_rfc1918')
            action({'kind':'option','id':option['PK'],'status':1,'value':'1'})
            action({'kind':'option','id':option['PK'],'status':0})
    finally:
        fixture_request(write,'DELETE','/profiles/'+profile)
    inventory=controld.inventory(read)
    if any(p.get('PK')==profile for p in inventory['profiles']):raise ValueError('Fixture cleanup unverified')
    after=controld.policy_snapshot(read,endpoint,account_scope=provider['account_scope'])
    if management.fingerprint(after)!=before_hash:raise ValueError('Production policy changed during validation')
    return {'operations':operations,'fixture_deleted':True,'production_policy_unchanged':True,
            'association_validation':'real-production-read; writes-on-unassigned-profile'}


def validate_stream(token,provider,directory):
    stream=live_dns.Stream();state={};observed=threading.Event()
    def run():
        try:
            with closing(history.History(directory)) as store:
                def receive(raw):
                    store.now=history.instant(datetime.now(timezone.utc).isoformat())
                    store.import_live_dns(raw,provider['account_scope'],provider['endpoint'],collected=history.utc(store.now))
                    result=analytics.Analytics(store).batch([{'kind':'dns','view':'facts',
                        'start':history.utc(store.now-900000000),'end':history.utc(store.now+1000000),
                        'scope':{'endpoint':provider['endpoint']},'limit':10}])['results'][0]
                    if not result['data']['rows']:raise ValueError('Live observation not queryable')
                    state.update(state='persisted-and-queryable',count=len(result['data']['rows']),
                                 complete_checkpoints=store.db.execute('SELECT count(*) FROM checkpoints').fetchone()[0])
                    observed.set();stream.cancel()
                stream.run(token,provider,receive,lambda:state.update(connected=True))
        except BaseException as error:
            state['error_type']=type(error).__name__
            if isinstance(error,live_dns.LiveError):state['source_error']=str(error)
        finally:observed.set()
    worker=threading.Thread(target=run,name='TailD live acceptance');worker.start()
    observed.wait();worker.join()
    if state.get('state')!='persisted-and-queryable':raise ValueError('Live acceptance failed: '+state.get('error_type','no event')+'/'+state.get('source_error',''))
    state['worker_exited']=True
    return state


def validate_owner_stream(provider,directory):
    """Real SSE -> collector's single writer with no attached dashboard.

    Historical acquisition is deliberately isolated here; its real API overlap
    and replay contracts are verified separately, not inferred from this probe.
    """
    import runtime
    observed=threading.Event();original=history.History.import_live_dns
    def imported(store,*args,**kwargs):
        result=original(store,*args,**kwargs)
        if str(store.directory).lower()==str(Path(directory).resolve()).lower():observed.set()
        return result
    def no_backfill(*args,**kwargs):return {'slices_read':0,'pending_windows':[],'interrupted':True}
    with patch.object(history.History,'import_live_dns',imported),patch.object(runtime.ingestion,'dns_windows',side_effect=no_backfill):
        collector=runtime.Collector(directory,None,instance='acceptance-'+secrets.token_hex(8))
        collector.start()
        try:
            collector.command('configure',{'dns':True,'provider':{**provider,'account_type':'personal'}})
            observed.wait()
            assert not collector.window_attached
            collector.command('pause')
        finally:collector.close()
        assert collector.live_thread is None and collector.closed.is_set()
    with closing(history.History(directory)) as store:
        count=store.db.execute('SELECT count(*) FROM dns').fetchone()[0]
        assert count>0
    return {'persisted_without_window':True,'facts':count,'pause_and_shutdown_drained':True,
            'historical_acquisition':'isolated-fixture; not claimed as real CSV validation'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint',required=True)
    parser.add_argument('--stream-endpoint',required=True)
    parser.add_argument('--history',required=True)
    parser.add_argument('--receipt',required=True)
    parser.add_argument('--allow-test-profile-writes',action='store_true')
    args=parser.parse_args()
    token=credentials.CredentialStore().read();provider={'account_scope':'acceptance','endpoint':args.endpoint}
    receipt={'association_read':bool(management.Management().dispatch('management-read',{'endpoint':args.endpoint},provider)['profile'])}
    if args.allow_test_profile_writes:
        receipt['writes']=validate_writes(token,credentials.CredentialStore(credentials.WRITE_TARGET).read(),args.endpoint,provider)
        Path(args.receipt).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    receipt['stream']=validate_stream(token,{**provider,'endpoint':args.stream_endpoint,'instance':controld.analytics_instance(token)},args.history)
    receipt['owner_stream']=validate_owner_stream({**provider,'endpoint':args.stream_endpoint,
        'instance':controld.analytics_instance(token)},str(Path(args.history).with_name(Path(args.history).name+'-owner')))
    Path(args.receipt).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))


if __name__=='__main__':
    try:main()
    except BaseException as error:
        print('Control D acceptance failed: '+type(error).__name__,file=sys.stderr);raise SystemExit(1)
