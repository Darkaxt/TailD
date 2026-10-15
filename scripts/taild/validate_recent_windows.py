"""Actual native R26 workflow with held external policy and analytics workers."""
import argparse,copy,json,threading,time
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright,expect
import analytics,connectivity,controld,recent_dns
from test_connectivity import DaemonFixture
from test_management import snapshot
from validate_analytics_windows import NativeSession,populate,settled,capture_preview
from validate_categories_windows import controls_ready

def run(shell,output):
    output.mkdir(parents=True,exist_ok=False);reports=[]
    with sync_playwright() as playwright:
      for zoom in (100,150):
        root=output/str(zoom);root.mkdir();populate(root/'history')
        session=NativeSession(shell,root/'history',playwright,zoom=150 if zoom==150 else None)
        policy_entered,policy_release,query_entered,query_release,recent_entered,recent_release=(threading.Event() for _ in range(6))
        try:
            page=session.page;page.set_default_timeout(0);settled(page);errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            session.collector.connectivity=connectivity.Connectivity(None,call=DaemonFixture())
            session.collector.command('configure',{'provider':{'account_scope':'local','endpoint':'device','account_type':'personal','instance':'europe'}})
            policy=snapshot();policy['resources']['filters']['data']['filters'][0]['name']='Ads & Trackers'
            def seed():
                now=datetime.now(timezone.utc).isoformat()
                for question,action in (('blocked-r26.invalid','0'),('allowed-r26.invalid','1')):
                    session.collector.store.import_live_dns({'timestamp':now,'endpointId':'device','profileId':'profile',
                        'question':question,'rrType':'A','action':action,'trigger':'filter','triggerValue':'ads'},'local','device',collected=now)
            session.collector._commit(seed)
            def held_policy(*args):policy_entered.set();policy_release.wait();return copy.deepcopy(policy)
            query=analytics.Analytics._query;recent=recent_dns.read
            def held_query(engine,request,*args,**kwargs):
                if request['kind']=='traffic':query_entered.set();query_release.wait()
                return query(engine,request,*args,**kwargs)
            def held_recent(*args,**kwargs):recent_entered.set();recent_release.wait();return recent(*args,**kwargs)
            with patch.object(session.collector.management,'_read',held_policy),patch.object(analytics.Analytics,'_query',held_query),patch.object(recent_dns,'read',held_recent):
                page.locator('#view-refresh').click();query_entered.wait()
                started=time.perf_counter();page.locator('#nav-3').click();recent_entered.wait()
                expect(page.locator('#recent-loading')).to_be_visible()
                assert page.locator('#recent-loading .loading-dots span').first.evaluate('e=>getComputedStyle(e).animationName')=='loading-wave'
                expect(page.locator('#view-loading')).to_have_count(0)
                capture_preview(session,root/'recent-loading.png')
                recent_release.set();expect(page.locator('#management-recent tbody tr')).to_have_count(2)
                ready_ms=(time.perf_counter()-started)*1000;policy_entered.wait()
                assert not policy_release.is_set() and not query_release.is_set()
                expect(page.locator('#management-recent').get_by_role('button',name='Block',exact=True).first).to_be_disabled()
                expect(page.locator('#incident-dns-refresh')).to_be_enabled()
                page.locator('#incident-dns-search').fill('blocked-r26')
                expect(page.locator('#management-recent tbody tr')).to_have_count(1)
                expect(page.locator('#management-recent')).to_contain_text('blocked-r26.invalid')
                capture_preview(session,root/'recent-during-policy.png')
                page.locator('#category-tailscale').click();controls_ready(page)
                expect(page.locator('#connectivity-window')).to_contain_text('Test device')
                boxes=page.evaluate('''()=>[...document.querySelectorAll('.category-root')].map(button=>{
                  const icon=button.querySelector('taild-brand-mark,svg'),b=button.getBoundingClientRect(),i=icon.getBoundingClientRect();
                  return {id:button.id,button:b.width,icon:i.width,left:i.left-b.left,right:b.right-i.right};})''')
                assert all(abs(b['icon']-22)<.1 and abs(b['button']-40)<.1 and abs(b['left']-b['right'])<.1 for b in boxes),boxes
                capture_preview(session,root/'equal-icons.png')
                page.locator('#nav-3').click()
                expect(page.locator('#management-recent tbody tr')).to_have_count(2)
                if zoom==100:
                    page.set_viewport_size({'width':560,'height':800})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    page.screenshot(path=str(root/'recent-560.png'))
                policy_release.set();query_release.set()
                page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'",timeout=0)
                expect(page.locator('#management-recent')).to_contain_text('Ads & Trackers')
            # Policy failure must not discard independent recent observations.
            def denied(*args):raise controld.ControlDError('Synthetic denied',status=403,state='denied')
            with patch.object(session.collector.management,'_read',denied):
                page.locator('#management-reload').click()
                page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'",timeout=0)
                expect(page.locator('#management-recent tbody tr')).to_have_count(2)
                expect(page.locator('.incident-workspace>.error')).to_contain_text('denied')
                expect(page.locator('#management-recent').get_by_role('button',name='Block',exact=True).first).to_be_disabled()
                page.locator('#incident-dns-search').fill('allowed-r26')
                expect(page.locator('#management-recent tbody tr')).to_have_count(1)
            assert not errors,errors
            reports.append({'zoom':zoom,'url':page.url,'rows_before_policy_and_analytics_release':True,
                'search_independent':True,'actions_require_policy':True,'policy_failure_preserves_recent':True,
                'animated_center_loading':True,'icon_bounds':boxes,'host_ready_ms_including_held_capture':round(ready_ms,2),
                'no_provider_writes':True,'page_errors':errors})
        finally:
            recent_release.set();policy_release.set();query_release.set();session.close()
    report={'ok':True,'views':reports,'native_served':True,'external_boundaries_isolated':True}
    (output/'recent.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output.resolve())
