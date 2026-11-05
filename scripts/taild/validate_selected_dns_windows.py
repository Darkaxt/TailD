"""Real native selector -> owning collector -> scoped CSV/history -> rendered rows.

Default inputs are synthetic. An explicitly supplied private provider binding can
exercise its existing READ boundary in an isolated history; no policy writes.
"""
import argparse
import copy
from contextlib import ExitStack
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import time
import tempfile
import threading
from unittest.mock import patch
import controld
import history
import management
import runtime
from test_management import snapshot as policy_fixture
from test_runtime import IsolatedLiveStream
from validate_analytics_windows import NativeSession, END
from validate_desktop_windows import snapshot


def run(shell, output, *, provider=None, devices=None, clock=END, search='edge.invalid', expected=1):
    from playwright.sync_api import sync_playwright, expect
    if output.exists():raise FileExistsError('Use a new task-owned validation output')
    history.private_directory(output)
    process_temp=output/'process-temp';process_temp.mkdir()
    os.environ['TEMP']=os.environ['TMP']=str(process_temp);tempfile.tempdir=str(process_temp)
    authenticated=provider is not None
    provider=provider or {'account_scope':'local','endpoint':'device','account_type':'personal','instance':'acceptance'}
    devices=devices or [{'PK':'device','name':'Configured device'}, {'PK':'edge','name':'Selected device'}, {'PK':'empty','name':'Empty device'}]
    configured=provider['endpoint'];selected=next(d['PK'] for d in devices if d['PK']!=configured)
    now=datetime.fromisoformat(clock.replace('Z','+00:00'))
    fixture=policy_fixture()
    fixture['resources']['endpoints']['data']['devices']=[{**d,'profile':{'PK':'profile'}} for d in devices]
    calls=[];fetch=controld.activity_slice
    def activity(*args, **kwargs):
        endpoint=kwargs['endpoint'];calls.append(endpoint)
        if authenticated:return fetch(*args, **kwargs)
        start,end=args[3:5];rows=[]
        if endpoint!='empty':
            for stamp in (now-timedelta(seconds=1),now-timedelta(days=2)):
                value=stamp.isoformat()
                if controld._utc(start)<=stamp<controld._utc(end):
                    rows.append({'source':'controld-activity-csv','raw':{'timestamp':value,'endpointId':endpoint,
                        'question':endpoint+'.invalid','rrType':'A','action':'0','profileId':'profile'}})
        return {'source':'controld-activity-csv','collected_at_utc':clock,'query_window':{'start_inclusive':start,
            'end_inclusive':end},'endpoint_id':endpoint,'truncated':False,'rows':rows}
    with ExitStack() as stack:
        stack.enter_context(patch.object(controld,'utc_now',return_value=now))
        stack.enter_context(patch.object(controld,'activity_slice',activity))
        stack.enter_context(patch.object(runtime.live_dns,'Stream',IsolatedLiveStream))
        stack.enter_context(patch.object(management,'write',side_effect=AssertionError('Provider writes forbidden')))
        if not authenticated:
            stack.enter_context(patch.object(runtime.credentials.CredentialStore,'read',return_value='synthetic-read'))
            stack.enter_context(patch.object(controld,'inventory',return_value={'devices':devices}))
        playwright=stack.enter_context(sync_playwright())
        session=NativeSession(shell,output/'history',playwright,open_overview=False,now=lambda:clock)
        try:
            def policy(endpoint,*args,**kwargs):return {**copy.deepcopy(fixture),'endpoint':endpoint}
            session.collector.management._read=policy
            session.collector.command('configure',{'provider':provider,'dns':True})
            page=session.page;page.set_default_timeout(0);page.clock.set_fixed_time(now)
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.locator('#nav-3').click()
            page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'",timeout=0)
            expect(page.locator('#management-endpoint')).to_have_value(configured)
            started=time.perf_counter();page.locator('#management-endpoint').select_option(selected)
            page.wait_for_function("()=>document.querySelector('#incident-dns-source')?.textContent.trim()==='Updates: Polling' && document.querySelectorAll('#management-recent tbody tr').length>0",timeout=0)
            selected_seconds=time.perf_counter()-started
            self_binding=session.collector.command('state')['settings']['provider']
            assert self_binding==provider
            page.locator('#incident-dns-search').fill(search)
            page.wait_for_function("n=>document.querySelector('#management-recent .recent-content')?.getAttribute('aria-busy')==='false' && document.querySelectorAll('#management-recent tbody tr').length===n",arg=expected,timeout=0)
            rows=page.locator('#management-recent tbody tr');expect(rows).to_have_count(expected)
            assert all(search in q.lower() for q in rows.locator('td:nth-child(2)').all_text_contents())
            assert page.locator('#incident-dns-source').inner_text().strip()=='Updates: Polling'
            selected_snapshot=snapshot(page)
            page.screenshot(path=str(output/'selected-endpoint.png'))
            stale_checked=False
            if not authenticated:
                entered=threading.Event();release=threading.Event();dispatch=session.collector.dispatch
                def held(request,**kwargs):
                    body=request.get('body',{})
                    if request.get('op')=='recent-dns' and body.get('endpoint')==selected and not body.get('search'):
                        entered.set();release.wait()
                    return dispatch(request,**kwargs)
                session.collector.dispatch=held
                try:
                    page.locator('#incident-dns-search').fill('');entered.wait()
                    page.evaluate('''configured=>{window.__wrongEndpointRows=false;
                      window.__endpointObserver=new MutationObserver(()=>{
                        if(document.querySelector('#management-endpoint')?.value===configured &&
                          [...document.querySelectorAll('#management-recent tbody tr')].some(r=>r.textContent.includes('edge.invalid')))
                          window.__wrongEndpointRows=true;});
                      window.__endpointObserver.observe(document.querySelector('#management-recent'),{childList:true,subtree:true});}''',configured)
                    page.locator('#management-endpoint').select_option(configured);release.set()
                    page.wait_for_function("()=>document.querySelector('#incident-dns-source')?.textContent.trim()==='Live stream: connected' && document.querySelectorAll('#management-recent tbody tr').length>0",timeout=0)
                    assert not page.evaluate('window.__wrongEndpointRows'),'Stale selected rows appeared under configured endpoint'
                    page.evaluate('window.__endpointObserver.disconnect()');stale_checked=True
                finally:release.set();session.collector.dispatch=dispatch
            else:
                page.locator('#incident-dns-search').fill('')
                page.locator('#management-endpoint').select_option(configured)
            page.wait_for_function("()=>document.querySelector('#incident-dns-source')?.textContent.trim()==='Live stream: connected' && document.querySelectorAll('#management-recent tbody tr').length>0",timeout=0)
            configured_count=page.locator('#management-recent tbody tr').count()
            if not authenticated:
                page.locator('#management-endpoint').select_option('empty')
                page.wait_for_function("()=>document.querySelector('#incident-dns-source')?.textContent.trim()==='Updates: Polling' && document.querySelector('#management-recent .recent-content')?.getAttribute('aria-busy')==='false' && document.querySelectorAll('#management-recent tbody tr').length===0",timeout=0)
                assert 'Connected' not in page.locator('#incident-dns-source').inner_text()
            page.set_viewport_size({'width':850,'height':800})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert not errors, errors
            report={'verified':True,'authenticated_provider_csv':authenticated,'capture_cutoff_utc':clock,
                'policy_fixture_only':True,'sse_fixture_only':True,'selected_search_rows':expected,
                'configured_visible_rows':configured_count,'configured_binding_unchanged':True,
                'selected_status':'Updates: Polling','selected_empty_checked':not authenticated,
                'stale_endpoint_reply_checked':stale_checked,
                'selection_to_rows_and_poll_completion_seconds':selected_seconds,'renderer':selected_snapshot,
                'served_url':page.url,'viewport_minimum_checked':850,'page_errors':errors,
                'source_requests':len(calls),'provider_writes':False,'production_history_used':False,
                'installed_client_changed':False,'served_assets':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (shell.parent/'ui').iterdir() if p.is_file()}}
            (output/'validation.json').write_text(json.dumps(report,indent=2))
            print(json.dumps({k:v for k,v in report.items() if k not in ('renderer','served_assets')}),flush=True)
        finally:session.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output)
