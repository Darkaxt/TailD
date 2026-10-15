"""Native progressive rendering, supersession and error recovery; isolated only."""
import argparse,hashlib,json,threading,time
from pathlib import Path
from unittest.mock import patch

import analytics
from validate_analytics_windows import NativeSession,populate,settled,START,END,select_range,export_ui
from validate_desktop_windows import snapshot


def run(shell,output):
    from playwright.sync_api import sync_playwright,expect
    output.mkdir(parents=True,exist_ok=False);populate(output/'history')
    release=threading.Event();entered=threading.Event();hold={'active':True,'error':False}
    original=analytics.Analytics._query
    def query(engine,request,revision,prepared=None):
        if request['kind']=='traffic' and request['view']=='summary' and hold['active']:
            entered.set();release.wait()
            if hold['error']:raise analytics.QueryError('Synthetic held dashboard failure')
        return original(engine,request,revision,prepared)
    with sync_playwright() as playwright,patch.object(analytics.Analytics,'_query',query):
        started=time.perf_counter();session=NativeSession(shell,output/'history',playwright)
        try:
            page=session.page;page.set_default_timeout(0)
            page.wait_for_function("()=>document.querySelector('#view-progress') && document.querySelector('#dashboard-dns-trend svg') && document.querySelector('#view-loading')===null")
            assert entered.is_set(),'Traffic was not actually held'
            expect(page.locator('main')).to_have_attribute('aria-busy','true')
            assert page.locator('fieldset.shared-scope').evaluate('(node)=>getComputedStyle(node).opacity')=='1','Sticky controls reveal charts while disabled'
            expect(page.locator('#dns-card span')).to_have_text('125')
            expect(page.locator('#received-card span')).to_have_text('Loading…')
            expect(page.locator('.screen-reader-progress')).to_have_count(1)
            assert page.locator('main .screen-reader-progress').count()==0,'Announcement is trapped inside aria-busy'
            assert page.locator('#analytics-results').count()==0 # No alternative browser surface.
            partial=snapshot(page);dns_ready=time.perf_counter()-started
            assert page.locator('.analytics-results').get_attribute('inert') is not None
            expect(page.locator('#nav-1')).to_be_enabled()
            page.screenshot(path=str(output/'pending.png'))
            # Navigation is accepted immediately; old progress must not reappear.
            page.locator('#nav-1').click();expect(page.locator('h1')).to_have_text('Applications')
            page.locator('#nav-2').click();expect(page.locator('h1')).to_have_text('Activity')
            hold['active']=False;release.set();settled(page)
            expect(page.locator('#fact-count')).to_have_text('125 facts')
            expect(page.locator('#dashboard-dns-trend')).to_have_count(0)
            page.locator('#nav-0').click();settled(page)
            prior=page.locator('#received-card span').inner_text();revision=page.locator('main').get_attribute('data-revision')
            # An error after partial progress restores the previous committed view.
            hold.update(active=True,error=True);release.clear();entered.clear()
            page.locator('#view-refresh').click()
            page.wait_for_function("()=>document.querySelector('#view-progress')!==null")
            assert entered.wait(10),'Diagnostic: held refresh did not start'
            release.set()
            page.wait_for_function("()=>document.querySelector('main').getAttribute('aria-busy')==='false'")
            expect(page.locator('#analytics-error')).to_be_visible()
            expect(page.locator('#received-card span')).to_have_text(prior)
            assert page.locator('main').get_attribute('data-revision')==revision
            hold.update(active=False,error=False);page.locator('#view-refresh').click();settled(page)
            select_range(page,START,END)
            summary=page.locator('#received-card small').inner_text()
            page.locator('#received-card').click();settled(page)
            expect(page.locator('#fact-count')).to_have_text('125 facts')
            export_ui(session,'json',output/'evidence.json')
            evidence=json.loads((output/'evidence.json').read_text())
            assert len(evidence['result']['data']['rows'])==125
            assert sum(int(r['inbound_bytes']) for r in evidence['result']['data']['rows'])==int(summary.split()[0])
            # Close the actual native window while a query is held. Hiding is an
            # immediate native transition; receipt/transaction completion still
            # follows the original operation, with no forced termination.
            hold['active']=True;release.clear();entered.clear()
            page.locator('#nav-0').click()
            page.wait_for_function("()=>document.querySelector('#view-progress')!==null")
            assert entered.wait(10),'Diagnostic: close probe query did not enter'
            import win32con,win32gui,win32process
            windows=[]
            win32gui.EnumWindows(lambda w,_:windows.append(w) if win32process.GetWindowThreadProcessId(w)[1]==session.native.pid and win32gui.IsWindowVisible(w) else None,None)
            assert len(windows)==1
            # SendMessage returns after the native close handler yields. WebView
            # document.visibilityState is not an authority for Form visibility.
            win32gui.SendMessage(windows[0],win32con.WM_CLOSE,0,0)
            assert not win32gui.IsWindowVisible(windows[0])
            release.set();session.native.wait()
            report={'ok':True,'url':page.url,'dns_before_held_traffic':True,'pending_native_render':partial,
                'dns_ready_elapsed_seconds':dns_ready,'timing_origin':'before native session launch; includes WebView startup, not physical presentation',
                'navigation_supersedes_progress':True,'error_restores_committed_view':True,'refresh_recovery':True,
                'exact_drilldown_export':True,'close_visible_window_during_held_query':True,'installed_client_changed':False,
                'served_assets':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (shell.parent/'ui').glob('*.js')}}
            (output/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('pending_native_render','served_assets')}))
        finally:release.set();session.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output)
