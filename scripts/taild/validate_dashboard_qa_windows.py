"""Native R15d regression workflows over isolated history; no installed changes."""
import argparse,json,threading
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
import analytics,history,ingestion
from validate_analytics_windows import NativeSession,populate,settled,select_range,START,END
from validate_desktop_windows import snapshot


def run(shell,output):
    output.mkdir(parents=True,exist_ok=False);home=output/'history';populate(home)
    store=history.History(home,now=END)
    store.import_traffic({'source':'glasswire-sqlite-observed-v1','collected_at_utc':END,
        'generation':{'traffic_database':{'file_id':'other'},'application_database':{'file_id':'other'}},
        'query_window':{'start_inclusive':START,'end_exclusive':END},'truncated':False,'rows':[]},'other-host')
    analytics.Analytics(store).record_context('other-host',{'source':'taildns-cli-readonly','captured_at_utc':START,
        'observed_until_utc':END,'coverage_method':'observed-change-stream','backend_state':'Running',
        'node_id':'other-node','user_id':'synthetic-user','dns_accepted':False,'local_override':False,
        'resolver_applied':False,'portal_mode':False})
    store.close()
    with sync_playwright() as playwright:
        session=NativeSession(shell,home,playwright);page=session.page;page.set_default_timeout(0)
        release=threading.Event();entered=threading.Event();original=session.collector.dispatch
        try:
            settled(page);select_range(page,START,END)
            page.locator('#scope-host').select_option('synthetic-host');settled(page)
            page.locator('#scope-device').select_option('synthetic-node');settled(page)
            page.locator('#scope-host').select_option('other-host');settled(page)
            expect(page.locator('#scope-device')).to_have_value('')
            page.locator('#scope-host').select_option('');settled(page)
            page.locator('#nav-2').click();settled(page)
            page.locator('#saved-name').fill('Deferred navigation')
            def held_save(request,**kwargs):
                if request.get('op')=='saved-query' and request.get('body',{}).get('action')=='save':
                    entered.set();release.wait()
                return original(request,**kwargs)
            session.collector.dispatch=held_save
            page.locator('#save-query').click();entered.wait()
            page.locator('#nav-1').click();expect(page.locator('h1')).to_have_text('Applications')
            release.set();settled(page)
            expect(page.locator('#application-table tbody tr')).to_have_count(3)
            session.collector.dispatch=original
            # Bypass only the renderer admission limit to exercise the native
            # protocol's own rejection receipt. Four admitted messages are held
            # behind the real serial owner bridge; the fifth must settle.
            release.clear();entered.clear()
            def held_state(request,**kwargs):
                if request.get('op')=='state':entered.set();release.wait()
                return original(request,**kwargs)
            session.collector.dispatch=held_state
            page.evaluate('''()=>{window.qaReceipts=[];chrome.webview.addEventListener('message',e=>{
              if(e.data.id>=90001&&e.data.id<=90005)window.qaReceipts.push(e.data)});
              for(let id=90001;id<=90005;id++)chrome.webview.postMessage({id,op:'state',body:{}})}''')
            entered.wait()
            page.wait_for_function("()=>window.qaReceipts.some(r=>r.id===90005&&r.ok===false&&r.state==='backpressure')",timeout=0)
            release.set();page.wait_for_function('()=>window.qaReceipts.length===5',timeout=0)
            assert page.evaluate('window.qaReceipts.filter(r=>r.ok).length')==4
            session.collector.dispatch=original
            # Explicit Refresh acknowledges acquisition, so Pause and actual
            # window close remain available while the source is still held.
            release.clear();entered.clear()
            from unittest.mock import patch
            def held_traffic(*args,**kwargs):
                entered.set();release.wait();return {'slice_attempts':0,'pending_windows':[],'interrupted':True}
            with patch.object(ingestion,'traffic_window',held_traffic):
                page.locator('#nav-5').click();settled(page)
                page.locator('#traffic-toggle').check();entered.wait()
                expect(page.locator('#autosave-status')).to_have_text('Settings save automatically')
                page.locator('#refresh').click()
                expect(page.locator('#autosave-status')).to_have_text('Settings save automatically')
                expect(page.locator('#pause-resume')).to_be_enabled()
                page.locator('#pause-resume').click();expect(page.locator('#collector-status')).to_have_text('paused')
                rendered=snapshot(page)
                import win32con,win32gui,win32process
                windows=[]
                win32gui.EnumWindows(lambda w,_:windows.append(w) if win32process.GetWindowThreadProcessId(w)[1]==session.native.pid and win32gui.IsWindowVisible(w) else None,None)
                assert len(windows)==1
                win32gui.SendMessage(windows[0],win32con.WM_CLOSE,0,0)
                assert not win32gui.IsWindowVisible(windows[0])
                session.native.wait() # Must finish before the held source is released.
                assert not release.is_set()
                release.set()
            report={'ok':True,'url':page.url,'host_change_clears_incompatible_node':True,
                'navigation_after_deferred_save':True,'native_overflow_receipt':True,
                'refresh_receipt_pause_close_during_held_source':True,'installed_client_changed':False,
                'rendered':rendered}
            (output/'qa-validation.json').write_text(json.dumps(report,indent=2))
            print(json.dumps({k:v for k,v in report.items() if k!='rendered'}))
        finally:release.set();session.collector.dispatch=original;session.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output)
