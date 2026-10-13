"""Actual WebView2 control/lifecycle verification using an isolated native source.

Explicitly launches only the task-built TailD window; no installed client changes.
Uses app-owned debug readiness, real checkbox/button events and an OS WM_CLOSE.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import uuid

import reader
import test_runtime


def close_window(process):
    import win32gui, win32process, win32con
    windows=[]
    def collect(window,_):
        if win32process.GetWindowThreadProcessId(window)[1]==process.pid and win32gui.IsWindowVisible(window):
            windows.append(window)
    win32gui.EnumWindows(collect,None)
    if len(windows)!=1:
        raise AssertionError('Expected exact owned visible collection window')
    win32gui.PostMessage(windows[0],win32con.WM_CLOSE,0,0)


def snapshot(page):
    return page.evaluate('''() => ({url:location.href,viewport:{width:innerWidth,height:innerHeight,
      unit:'CSS px',device_pixel_ratio:devicePixelRatio},coverage:'all named controls, panels and statuses',
      assets:{scripts:[...document.scripts].map(e=>e.src),styles:[...document.querySelectorAll('link[rel="stylesheet"]')].map(e=>e.href)},
      truncated:false, nodes:[...document.querySelectorAll('input,button,select,h1,h2,[role="status"],.rail,app-dashboard-widget')].map((e,index)=>{
        const r=e.getBoundingClientRect(),s=getComputedStyle(e);
        return {id:e.id||e.getAttribute('aria-label')||e.tagName.toLowerCase()+'-'+index,
          parent:e.parentElement?.id||e.parentElement?.tagName.toLowerCase(),role:e.getAttribute('role')||e.tagName.toLowerCase(),
          text:e.type==='password'?'[redacted]':e.textContent?.trim(),bounds:{x:r.x,y:r.y,width:r.width,height:r.height,unit:'CSS px'},
          visible:s.visibility!=='hidden'&&s.display!=='none'&&r.width>0&&r.height>0,
          enabled:!e.disabled,selected:typeof e.checked==='boolean'?e.checked:null,focused:document.activeElement===e,
          actions:['BUTTON','INPUT','SELECT'].includes(e.tagName)?['user-input']:[]}}),
      layout:{document_width:document.documentElement.scrollWidth,viewport_width:innerWidth},
      timing:{origin:'performance.timeOrigin',navigation:performance.getEntriesByType('navigation').map(e=>({
        dom_content_loaded_ms:e.domContentLoadedEventEnd,load_event_ms:e.loadEventEnd})),presented_frame:null},
      limitations:['Native frame presentation not measured','Off-screen controls need scrolling','No physical sleep/wake evidence']})''')


def collection_controls(page):
    from playwright.sync_api import expect
    expect(page.locator('main')).to_have_attribute('aria-busy','false')
    page.locator('#nav-5').click()
    expect(page.locator('#traffic-toggle')).to_be_visible()


def run(shell, output):
    import win32api,win32event
    from playwright.sync_api import sync_playwright,expect
    output.mkdir(parents=True,exist_ok=False)
    # Reuse the existing native SQLite/WAL fixture and real collector. These are
    # synthetic source records, not a mock transport or installed-user history.
    fixture=test_runtime.RuntimeTest('test_opt_in_acquire_query_pause_resume_restart_without_duplicates')
    fixture.fixture_root=output/'source-fixture'
    fixture.setUp()
    fixture.collector.instance='ui-'+uuid.uuid4().hex
    control=reader.PipeServer(fixture.collector.instance,reader.current_sid(),fixture.collector)
    control_error=[]
    ready=threading.Event()
    def serve_control():
        try:
            # Surface startup failure as an actual transition, not a quiet
            # readiness wait whose only signaling thread has already failed.
            watcher=threading.Thread(target=lambda:(control.ready.wait(),ready.set()))
            watcher.start()
            control.serve()
        except BaseException as error:
            control_error.append(type(error).__name__)
        finally:
            control.ready.set()
            watcher.join()
            ready.set()
    thread=threading.Thread(target=serve_control,name='TailD UI validation owner pipe')
    thread.start();ready.wait()
    if control_error:
        fixture.doCleanups()
        raise AssertionError('Control pipe startup failed: '+control_error[0])
    native=None
    reports=[]
    try:
        def open_ui(playwright,ordinal):
            nonlocal native
            with socket.socket() as available:
                available.bind(('127.0.0.1',0));port=available.getsockname()[1]
            name='Local\\Darkaxt.TailD.UIReady.'+fixture.collector.instance
            event=win32event.CreateEvent(None,True,False,name)
            try:
                native=subprocess.Popen([str(shell),'--instance',fixture.collector.instance,
                    '--collector-pid',str(os.getpid()),'--user-data',str(fixture.home/('ui-cache-'+str(ordinal))),
                    '--debug-port',str(port),'--validation-ready-event',name],
                    creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                selected=win32event.WaitForMultipleObjects([event,int(native._handle)],False,win32event.INFINITE)
                if selected!=win32event.WAIT_OBJECT_0:
                    stdout,stderr=native.communicate()
                    raise AssertionError('Native UI exited before readiness: '+stderr.decode(errors='replace'))
            finally:
                win32api.CloseHandle(event)
            browser=playwright.chromium.connect_over_cdp('http://127.0.0.1:'+str(port))
            context=browser.contexts[0]
            page=context.pages[0]
            page.set_default_timeout(15000) # Diagnostic boundary only; never kills underlying operation.
            collection_controls(page)
            assert page.url=='https://taild.local/index.html','Actual packaged page did not load'
            return browser,page
        with sync_playwright() as playwright:
            browser,page=open_ui(playwright,1)
            errors=[];page.on('pageerror',lambda error:errors.append(type(error).__name__))
            response=page.reload()
            assert response is not None
            csp=response.headers.get('content-security-policy','')
            assert "script-src 'self'" in csp and "connect-src 'none'" in csp
            assert 'unsafe-eval' not in csp and "script-src 'self' 'unsafe-inline'" not in csp
            collection_controls(page)
            expect(page.locator('#traffic-toggle')).not_to_be_checked()
            for width,height in ((1440,900),(1280,800),(1024,768)):
                page.set_viewport_size({'width':width,'height':height})
                expect(page.locator('#stop-collector')).to_be_visible()
                measured=snapshot(page)
                assert measured['layout']['document_width']<=width,'Unexpected horizontal overflow'
                reports.append(measured)
                page.screenshot(path=str(output/f'controls-{width}x{height}.png'),full_page=True)
            page.locator('#traffic-toggle').focus()
            assert page.locator('#traffic-toggle').evaluate('(e)=>e===document.activeElement')
            # Fuzz the displayed source text without executing a backend action.
            # This is renderer injection evidence, not a claim of live vendor text.
            unsafe='<img src=x onerror="window.__taildInjection=1">'
            fixture.collector.sources['context']={'state':unsafe}
            page.reload()
            collection_controls(page)
            expect(page.locator('#context-status')).to_have_text(unsafe)
            assert page.locator('#context-status img').count()==0
            assert page.evaluate('window.__taildInjection===undefined')
            fixture.collector.sources['context']={'state':'not-configured'}
            page.reload()
            collection_controls(page)
            # Real event path: checkbox -> Angular CVA -> native allowlist -> owner pipe -> SQLite acquisition.
            page.locator('#traffic-toggle').check()
            expect(page.locator('#traffic-toggle')).to_be_checked()
            expect(page.locator('#autosave-status')).to_have_text('Settings save automatically')
            page.locator('#refresh').click()
            expect(page.locator('#autosave-status')).to_have_text('Settings save automatically')
            expect(page.locator('#traffic-status')).to_have_text('collecting')
            assert fixture.query()[1]['results'][0]['data']['total_count']==1
            page.locator('#pause-resume').click()
            expect(page.locator('#collector-status')).to_have_text('paused')
            page.locator('#pause-resume').click()
            expect(page.locator('#pause-resume')).to_have_text('Pause collection')
            expect(page.locator('#traffic-status')).to_have_text('collecting')
            reports.append(snapshot(page))
            page.screenshot(path=str(output/'controls-enabled.png'),full_page=True)
            # Real OS window-close action, not a backend invocation disguised as a click.
            close_window(native)
            assert native.wait()==0
            browser.close()
            assert not fixture.collector.closing
            assert fixture.query()[1]['results'][0]['data']['total_count']==1
            browser,page=open_ui(playwright,2)
            expect(page.locator('#traffic-toggle')).to_be_checked()
            page.locator('#stop-collector').click()
            assert native.wait()==0
            browser.close()
            assert fixture.collector.closed.wait(15),'Diagnostic: explicit stop incomplete'
            assert not errors,errors
            # Verify the ordinary source-build launcher, including automatic
            # unelevated worker startup, disabled teardown and recovery entrypoint.
            fixture.client.close()
            import history
            home=fixture.root/'bootstrap-history'
            history.History(home).close()
            instance='owner-'+history.digest([reader.current_sid(),str(home.resolve()).casefold()])[:32]
            with socket.socket() as available:
                available.bind(('127.0.0.1',0));port=available.getsockname()[1]
            event_name='Local\\Darkaxt.TailD.UIReady.'+instance
            event=win32event.CreateEvent(None,True,False,event_name)
            launcher=None
            try:
                launcher=subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('desktop.py')),
                    '--shell',str(shell),'--history',str(home),'--reader-instance',fixture.server.name.rsplit('.',1)[-1],
                    '--debug-port',str(port),'--validation-ready-event',event_name],creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                selected=win32event.WaitForMultipleObjects([event,int(launcher._handle)],False,win32event.INFINITE)
                if selected!=win32event.WAIT_OBJECT_0:
                    _,stderr=launcher.communicate()
                    raise AssertionError('Desktop launcher exited before readiness: '+stderr.decode(errors='replace'))
                browser=playwright.chromium.connect_over_cdp('http://127.0.0.1:'+str(port))
                page=browser.contexts[0].pages[0]
                collection_controls(page)
                expect(page.locator('#collector-status')).to_have_text('Disabled',ignore_case=True)
                page.locator('#stop-collector').click()
                assert launcher.wait()==0
                browser.close()
            finally:
                win32api.CloseHandle(event)
                if launcher is not None and launcher.poll() is None:
                    import psutil
                    for child in psutil.Process(launcher.pid).children():
                        if child.name()=='TailD.Desktop.exe':close_window(child)
                    launcher.wait()
        evidence={'state':'passed','source':'isolated native SQLite/WAL fixture','actual_protected_source':'separate runtime-validation.json',
            'window_close_enabled_collection':True,'reopen_preserves_opt_in':True,'explicit_stop':True,
            'actual_user_event_path':True,'vpn_or_firewall_changed':False,'physical_sleep_wake':False,
            'actual_asset_csp':csp,'literal_source_text_injection_denied':True,'keyboard_focus':True,
            'source_build_launcher_start_stop':True,
            'build_sha256':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in
                [shell,shell.with_suffix('.dll'),*(shell.parent/'ui').glob('*.js'),*(shell.parent/'ui').glob('*.css')]},
            'snapshots':reports}
        (output/'desktop-validation.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in evidence.items() if k!='snapshots'}))
    finally:
        if native is not None and native.poll() is None:
            close_window(native);native.wait()
        control.stop();thread.join()
        fixture.doCleanups()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.shell.resolve(strict=True),args.output)


if __name__=='__main__':main()
