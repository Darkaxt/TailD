"""Complete native desktop analytics workflow; no installed client changes.

Synthetic counter/security contracts plus a read-only snapshot of retained real
GlassWire history. UI Automation operates the owned native save dialog; ordinary
Playwright actions operate actual packaged Angular assets, not a browser mock.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import threading
import uuid

import analytics
import history
import reader
import runtime
from validate_desktop_windows import snapshot

START='2026-10-13T10:00:00Z'
END='2026-10-13T10:20:00Z'


def populate(directory):
    with_store=history.History(directory,now=END)
    rows=[]
    hostile='=synthetic <img src=x onerror="window.__taildInjection=1">.exe'
    for i in range(125):
        timestamp=history.instant(START)+(i*5+1)*1000000
        rows.append({'timestamp_utc':history.utc(timestamp),'timestamp_raw':timestamp//1000000,
            'application_id':42,'application_path':hostile if i%3==0 else ('C:\\Synthetic\\normal.exe' if i%3==1 else 'D:\\Other\\normal.exe'),
            'destination_ip':'198.51.100.2' if i%2 else '198.51.100.3','destination_port':443,'protocol_raw':97,'flags_raw':0,
            'destination_status':'observed-ipv4-little-endian','inbound_bytes':2**53+9 if i==0 else i+100,'outbound_bytes':i+20,
            'provenance':{'rowid':i+1,'remote_host_blob_sha256':str(i%2),'application_blob_sha256':str(i%3)}})
    traffic={'source':'glasswire-sqlite-observed-v1','collected_at_utc':END,
        'generation':{'traffic_database':{'file_id':'synthetic-1'},'application_database':{'file_id':'synthetic-2'}},
        'query_window':{'start_inclusive':START,'end_exclusive':END},'truncated':True,'rows':rows}
    with_store.import_traffic(traffic,'synthetic-host')
    dns={'source':'controld-activity-csv','collected_at_utc':END,'endpoint_id':'synthetic-endpoint',
         'query_window':traffic['query_window'],'truncated':False,'rows':[
           {'source':'controld-activity-csv','raw':{'timestamp':history.utc(history.instant(r['timestamp_utc'])-1000000),
            'endpointId':'synthetic-endpoint','question':'synthetic.invalid','answers':r['destination_ip'],
            'rrType':'A','action':('-1','0','1','2','3','unverified-code')[i%6],'trigger':'synthetic-reason','answerCountryCode':'DE','answerASN':'64500'}} for i,r in enumerate(rows)]}
    with_store.import_dns(dns,'synthetic-account','synthetic-endpoint')
    engine=analytics.Analytics(with_store)
    engine.record_context('synthetic-host',{'source':'taildns-cli-readonly','captured_at_utc':START,'observed_until_utc':END,
        'coverage_method':'observed-change-stream','resolver_endpoint':'synthetic-endpoint','backend_state':'Running','node_id':'synthetic-node','user_id':'synthetic-user',
        'dns_accepted':True,'local_override':True,'resolver_applied':True,'portal_mode':False,'endpoint_exclusivity':'unverified'})
    engine.record_policy({'source':'controld-api-readonly','account_scope':'synthetic-account','endpoint':'synthetic-endpoint','profile':'synthetic-profile',
        'captured_at_utc':history.utc(history.instant(END)-1000000),'consistency':'separate-api-reads','historical_rule_causality':'not-established',
        'resources':{'rules':{'state':'available','route':'synthetic GET contract','data':[{'name':'Synthetic literal rule','action':'unverified'}]},
                     'services':{'state':'unavailable','reason':'Synthetic missing capability'}}})
    total=sum(r['inbound_bytes']+r['outbound_bytes'] for r in rows)
    with_store.close()
    return total


def close_owned(process):
    import win32con,win32gui,win32process
    windows=[]
    win32gui.EnumWindows(lambda w,_:windows.append(w) if win32process.GetWindowThreadProcessId(w)[1]==process.pid and win32gui.IsWindowVisible(w) else None,None)
    # Close modal first, then its parent. No unrelated app/window is touched.
    for window in sorted(windows,key=lambda w:win32gui.GetClassName(w)!='#32770'):
        win32gui.PostMessage(window,win32con.WM_CLOSE,0,0)
    process.wait()


class NativeSession:
    def __init__(self,shell,directory,playwright,zoom=None):
        import win32api,win32event
        self.directory=directory;self.collector=runtime.Collector(directory,None,now=lambda:END,instance='analytics-'+uuid.uuid4().hex)
        self.collector.start()
        self.server=reader.PipeServer(self.collector.instance,reader.current_sid(),self.collector)
        self.thread=threading.Thread(target=self.server.serve);self.thread.start();self.server.ready.wait()
        self.native=None;self.browser=None
        try:
            with socket.socket() as available:available.bind(('127.0.0.1',0));port=available.getsockname()[1]
            name='Local\\Darkaxt.TailD.UIReady.'+self.collector.instance
            event=win32event.CreateEvent(None,True,False,name)
            try:
                self.native=subprocess.Popen([str(shell),'--instance',self.collector.instance,'--collector-pid',str(os.getpid()),
                    '--user-data',str(directory/'ui-cache'),'--debug-port',str(port),'--validation-ready-event',name,
                    *(['--validation-zoom',str(zoom)] if zoom else [])],
                    creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                observed=win32event.WaitForMultipleObjects([event,int(self.native._handle)],False,win32event.INFINITE)
                if observed!=win32event.WAIT_OBJECT_0:raise AssertionError('Native analytics exited before navigation readiness')
            finally:win32api.CloseHandle(event)
            self.browser=playwright.chromium.connect_over_cdp('http://127.0.0.1:'+str(port))
            self.page=self.browser.contexts[0].pages[0];self.page.set_default_timeout(20000)
        except BaseException:self.close();raise

    def close(self):
        try:
            if self.native is not None and self.native.poll() is None:close_owned(self.native)
            if self.browser is not None:
                try:self.browser.close()
                except Exception:
                    # Playwright can already have closed its loop during failed
                    # validation. Native process exit is independently observed.
                    if self.native is not None and self.native.poll() is None:raise
        finally:
            self.server.stop();self.thread.join();self.collector.close()


def settled(page):
    from playwright.sync_api import expect
    # A five-second assertion deadline is not query completion. Observe the
    # original generation's actual terminal transition, including slow history.
    page.wait_for_function("()=>document.querySelector('main')?.getAttribute('aria-busy')==='false'",timeout=0)
    error=page.locator('#analytics-error')
    assert error.count()==0,'Desktop query failed (inspect private renderer evidence)'
    expect(page.locator('main')).to_have_attribute('data-ready','true')


def select_range(page,start,end):
    page.locator('#time-range').select_option('custom');settled(page)
    page.locator('#utc-start').fill(start)
    page.locator('#utc-start').press('Tab');settled(page)
    page.locator('#utc-end').fill(end)
    page.locator('#utc-end').press('Tab');settled(page)


def export_ui(session,format,destination):
    helper=subprocess.Popen(['powershell','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',
        str(Path(__file__).with_name('validate_export_dialog.ps1')),'-OwnerPid',str(session.native.pid),'-Destination',str(destination)],
        creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    marker=helper.stdout.readline().strip()
    if marker!='ready':
        out,err=helper.communicate();raise AssertionError('Native dialog observer failed to start: '+err)
    session.page.locator('#export-'+format).click()
    out,err=helper.communicate()
    if helper.returncode:raise AssertionError('Native dialog action failed: '+err)
    from playwright.sync_api import expect
    # Save dispatch is not completion; inspect the original operation's receipt.
    expect(session.page.locator('main')).to_have_attribute('aria-busy','false',timeout=20000)
    error=session.page.locator('#analytics-error')
    assert error.count()==0,'Native export failed: '+(error.inner_text() if error.count() else '')
    expect(session.page.locator('#export-status')).to_contain_text('Saved '+destination.name)
    assert destination.is_file()


def capture_preview(session,destination):
    """Actual WebView surface, not CDP's incorrect native-zoom clip or desktop occlusion."""
    import base64
    encoded=session.page.evaluate('''()=>new Promise((resolve,reject)=>{
      const id=910001;const receive=e=>{if(e.data.id!==id)return;
        chrome.webview.removeEventListener('message',receive);
        if(e.data.ok)resolve(e.data.data.png);else reject(new Error('Validation capture failed'))};
      chrome.webview.addEventListener('message',receive);
      chrome.webview.postMessage({id,op:'validation-capture',body:{}})})''')
    png=base64.b64decode(encoded,validate=True);assert png.startswith(b'\x89PNG\r\n\x1a\n')
    destination.write_bytes(png)


def duplicate_executable_drilldown(page):
    from playwright.sync_api import expect
    for path,count in (('C:\\Synthetic\\normal.exe',42),('D:\\Other\\normal.exe',41)):
        page.locator('#nav-1').click();settled(page)
        page.locator('#application-table .identity-link').filter(has_text='normal.exe').locator('xpath=..').get_by_title(path,exact=True).click()
        settled(page)
        page.get_by_role('button',name='Inspect application activity',exact=True).click();settled(page)
        expect(page.locator('#fact-count')).to_have_text(str(count)+' facts')
        assert set(page.locator('.fact-identity strong').evaluate_all('(nodes)=>nodes.map(n=>n.title)'))=={path}
        page.get_by_role('button',name='Remove application scope',exact=True).click();settled(page)


def dashboard_workflow(session,output):
    from playwright.sync_api import expect
    page=session.page
    expect(page.locator('#dashboard-stats .mini-stat')).to_have_count(6)
    expect(page.locator('#dashboard-dns-trend svg')).to_have_attribute('aria-label',
        'DNS decision counts. Exact values and scope links in chart data table.')
    expected=int(page.locator('#dns-card span').inner_text())
    counts=page.locator('#dashboard-dns-trend tbody tr').evaluate_all('(rows)=>rows.map(r=>Number(r.cells[1].textContent))')
    assert sum(counts)==expected==125
    original_revision=page.locator('main').get_attribute('data-revision')
    page.locator('#geography-mode').select_option('dns')
    tile=page.locator('.country-tile[data-country="DE"]');tile.focus()
    expect(page.locator('taild-world-map path[data-country="DE"]')).to_have_class('observed highlighted')
    assert page.locator('main').get_attribute('data-revision')==original_revision
    page.screenshot(path=str(output/'country-focus.png'),full_page=True)
    for control,destination in (('dashboard-provider','Control D'),('dashboard-health','Sources & health'),('dashboard-settings','Settings')):
        page.locator('#'+control).click();settled(page)
        expect(page.locator('h1')).to_have_text(destination)
        page.locator('#nav-0').click();settled(page)
    for control,mode in (('received-card','traffic'),('sent-card','traffic'),('buckets-card','traffic'),('dns-card','dns')):
        page.locator('#'+control).click();settled(page)
        expect(page.locator('#mode-'+mode)).to_have_attribute('aria-selected','true')
        expect(page.locator('#fact-count')).to_have_text('125 facts')
        page.locator('#nav-0').click();settled(page)
    page.locator('#applications-card').click();settled(page)
    expect(page.locator('#application-table tbody tr')).to_have_count(3)
    page.locator('#nav-0').click();settled(page)
    page.locator('#questions-card').click();settled(page)
    expect(page.locator('#group-by')).to_have_value('question')
    page.get_by_role('button',name='Inspect facts',exact=True).click();settled(page)
    expect(page.locator('#fact-count')).to_have_text('125 facts')
    page.get_by_role('button',name='Remove filter 1',exact=True).click();settled(page)
    page.locator('#nav-0').click();settled(page)
    # Partial first-bin drill-down must not reintroduce earlier events.
    clipped='2026-10-13T10:00:01Z';select_range(page,clipped,END)
    page.locator('#dashboard-dns-trend .chart-data > summary').click()
    first=page.locator('#dashboard-dns-trend tbody tr').first
    bin_events=int(first.locator('td').nth(1).inner_text())
    first.get_by_role('button').click();settled(page)
    expect(page.locator('#mode-dns')).to_have_attribute('aria-selected','true')
    expect(page.locator('#utc-start')).to_have_value(clipped)
    expect(page.locator('#fact-count')).to_have_text(str(bin_events)+' facts')
    export_ui(session,'json',output/'dns-bin-evidence.json')
    exported=json.loads((output/'dns-bin-evidence.json').read_text(encoding='utf-8'))
    assert exported['result']['data']['total_count']==bin_events
    assert exported['query']['kind']=='dns' and exported['query']['start']==clipped
    page.locator('#nav-0').click();settled(page);select_range(page,START,END)


def run(shell,output,real_history,policy_history):
    from playwright.sync_api import sync_playwright,expect
    import win32security
    if output.exists():raise AssertionError('Validation output must be new')
    history.private_directory(output)
    synthetic=output/'synthetic-history'
    expected_total=populate(synthetic)
    reports=[];sessions=[]
    try:
      with sync_playwright() as playwright:
        session=NativeSession(shell,synthetic,playwright);sessions.append(session);page=session.page
        errors=[];page.on('pageerror',lambda error:errors.append(type(error).__name__))
        settled(page);page.screenshot(path=str(output/'empty.png'),full_page=True);select_range(page,START,END)
        # Hold one real queued query at its worker boundary. The UI must not
        # mutate scope under an outstanding revision; navigation stays usable
        # (supersession is exercised by validate_dashboard_performance_windows).
        # Event based,
        # with no sleep, guessed duration, cancellation or mocked query result.
        held=threading.Event();release=threading.Event();original=session.collector.dispatch
        def pending_query(request,**kwargs):
            if request.get('op')=='view-query':held.set();release.wait()
            return original(request,**kwargs)
        try:
            session.collector.dispatch=pending_query
            page.locator('#view-refresh').click();held.wait()
            expect(page.locator('#scope-host')).to_be_disabled();expect(page.locator('#nav-1')).to_be_enabled()
            expect(page.locator('.analytics-results')).to_have_attribute('inert','')
            expect(page.locator('#view-loading')).to_be_visible()
            expect(page.locator('#view-loading')).to_contain_text('Refreshing view')
            page.screenshot(path=str(output/'refresh-loading.png'))
        finally:release.set();session.collector.dispatch=original
        settled(page)
        expect(page.locator('#view-loading')).to_have_count(0)
        expect(page.locator('taild-world-map .map-surface')).to_have_attribute('data-map-ready','true')
        assert page.locator('taild-world-map path').count()>150
        assert page.locator('.consumer-name',has_text='normal.exe').count()==2
        assert page.locator('.consumer-name',has_text='C:\\Synthetic').count()==0
        assert {p.split(' · ')[0] for p in page.locator('.consumer',has_text='normal.exe').evaluate_all('(nodes)=>nodes.map(n=>n.title)')}=={'C:\\Synthetic\\normal.exe','D:\\Other\\normal.exe'}
        expect(page.locator('#geography-mode')).to_have_value('dns')
        expect(page.locator('.country-tile[data-country="DE"]')).to_contain_text('125 decisions')
        expect(page.locator('#dashboard-outcomes')).to_contain_text('Blocked')
        germany=page.locator('taild-world-map path[data-country="DE"]')
        germany.focus();germany.press('Enter');settled(page)
        expect(page.locator('.filter-tags')).to_contain_text('provider_country eq DE')
        expect(page.locator('#fact-count')).to_have_text('125 facts')
        export_ui(session,'json',output/'provider-country-evidence.json')
        provider_export=json.loads((output/'provider-country-evidence.json').read_text())
        assert all(r['provider_country']=='DE' for r in provider_export['result']['data']['rows'])
        page.get_by_role('button',name='Remove filter 1',exact=True).click();settled(page)
        page.locator('#nav-0').click();settled(page)
        page.locator('#dashboard-outcomes .rank-table button').filter(has_text='Blocked').click();settled(page)
        expect(page.locator('.filter-tags')).to_contain_text('outcome eq block')
        expect(page.locator('#fact-count')).to_have_text('21 facts')
        export_ui(session,'json',output/'blocked-decision-evidence.json')
        blocked=json.loads((output/'blocked-decision-evidence.json').read_text())
        assert all(r['fact']['raw']['action']=='0' and r['outcome']=='block' for r in blocked['result']['data']['rows'])
        page.get_by_role('button',name='Remove filter 1',exact=True).click();settled(page)
        page.locator('#nav-0').click();settled(page)
        page.locator('#geography-mode').select_option('traffic')
        # Real synthetic answer metadata has one unique preceding candidate for
        # early buckets, and many later ambiguous buckets. Only inferred bytes
        # are highlighted, never unobserved countries or routes.
        germany=page.locator('taild-world-map path[data-country="DE"]')
        expect(germany).to_have_attribute('role','button')
        germany.focus();germany.press('Enter');settled(page)
        expect(page.locator('.filter-tags')).to_contain_text('destination_country eq DE')
        assert int(page.locator('#fact-count').inner_text().split()[0])>0
        page.get_by_role('button',name='Remove filter 1',exact=True).click();settled(page)
        page.locator('#nav-0').click();settled(page)
        expect(page.locator('#coverage-state')).to_have_text('partial traffic')
        page.locator('#scope-device').select_option('synthetic-node');settled(page)
        page.locator('#scope-device').select_option('');settled(page)
        expect(page.locator('#received-card small')).to_have_text(str(expected_total-sum(i+20 for i in range(125)))+' bytes')
        assert page.locator('sfng-netquery-line-chart svg').count()==2
        assert page.locator('sfng-netquery-circular-bar-chart svg path').count()>0
        assert page.locator('main img').count()==0 and page.evaluate('window.__taildInjection===undefined')
        dashboard_workflow(session,output)
        for width,height in ((1440,900),(1280,800),(1024,768)):
            page.set_viewport_size({'width':width,'height':height})
            page.locator('h1').scroll_into_view_if_needed()
            expect(page.locator('#received-card')).to_be_visible()
            measured=snapshot(page);assert measured['layout']['document_width']<=width
            if width==1440:
                bounds=page.locator('[id^="dashboard-"]').evaluate_all('(nodes)=>Object.fromEntries(nodes.map(n=>{const b=n.getBoundingClientRect();return [n.id,{x:b.x,y:b.y,width:b.width}]}))')
                assert bounds['dashboard-collection']['x']>bounds['dashboard-stats']['x']
                assert bounds['dashboard-dns-trend']['y']>bounds['dashboard-stats']['y']
                assert bounds['dashboard-map']['x']>bounds['dashboard-countries']['x']
            reports.append(measured);page.screenshot(path=str(output/f'overview-{width}x{height}.png'),full_page=True)
        page.set_viewport_size({'width':1440,'height':900})
        duplicate_executable_drilldown(page)
        page.locator('#nav-1').click();settled(page)
        expect(page.locator('#application-table tbody tr')).to_have_count(3)
        app_buttons=page.locator('#application-table .identity-link')
        app_buttons.nth(0).click();settled(page)
        app_id=page.locator('.filter-pill').first.inner_text()
        page.screenshot(path=str(output/'application.png'),full_page=True)
        page.get_by_role('button',name='Inspect application activity',exact=True).click();settled(page)
        scoped_count=int(page.locator('#fact-count').inner_text().split()[0]);assert scoped_count in (41,42)
        assert app_id.split('×')[0].strip() in page.locator('.filter-tags').inner_text()
        page.locator('.fact-entry > summary').first.click()
        expect(page.locator('taild-evidence').first).to_be_visible()
        # Only the expanded fact instantiates evidence, including its paginated
        # candidate table. Closed rows must not materialize repeated large data.
        expect(page.locator('taild-evidence')).to_have_count(1)
        candidates=page.locator('taild-evidence .candidate-evidence')
        if candidates.count():
            assert candidates.locator('tbody tr').count()<=20
            detail=candidates.locator('summary').first
            detail.focus();detail.press('Enter')
            expect(detail.locator('..')).to_have_attribute('open','')
        page.screenshot(path=str(output/'activity-evidence.png'),full_page=True)
        # Saved query is the exact scoped request, including application identity.
        page.locator('#saved-name').fill('Synthetic application')
        page.locator('#save-query').click();expect(page.locator('#export-status')).to_contain_text('Saved locally')
        page.get_by_role('button',name='Remove application scope',exact=True).click();settled(page)
        expect(page.locator('#fact-count')).to_have_text('125 facts')
        page.locator('#filter-field').select_option('destination_port');page.locator('#filter-op').select_option('eq')
        page.locator('#filter-value').fill('443');page.locator('#add-filter').click();settled(page)
        page.locator('#filter-field').select_option('total_bytes');page.locator('#filter-op').select_option('gt')
        page.locator('#filter-value').fill(str(2**53));page.locator('#add-filter').click();settled(page)
        expect(page.locator('#fact-count')).to_have_text('1 facts')
        page.get_by_role('button',name='Remove filter 2',exact=True).click();settled(page)
        page.get_by_role('button',name='Remove filter 1',exact=True).click();settled(page)
        first_ids=page.locator('.fact-entry').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.factId)')
        page.locator('#next-page').click();settled(page)
        second_ids=page.locator('.fact-entry').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.factId)')
        assert len(first_ids)==50 and len(second_ids)==50 and not set(first_ids)&set(second_ids)
        page.locator('#previous-page').click();settled(page)
        before_revision=page.locator('main').get_attribute('data-revision')
        # A real concurrent WAL writer changes only its own isolated history.
        with sqlite3.connect(synthetic/'history.sqlite3') as writer:
            writer.execute('UPDATE settings SET revision=revision+1');writer.commit()
        page.locator('#next-page').click()
        expect(page.locator('#analytics-error')).to_contain_text('History changed')
        expect(page.locator('#view-loading')).to_have_count(0)
        assert page.locator('main').get_attribute('data-revision')==before_revision
        page.locator('#view-refresh').click();settled(page)
        json_path=synthetic/'evidence.json';csv_path=synthetic/'analytics.csv'
        export_ui(session,'json',json_path);export_ui(session,'csv',csv_path)
        exported=json.loads(json_path.read_text(encoding='utf-8'))
        assert sum(int(r['total_bytes']) for r in exported['result']['data']['rows'])==expected_total
        with csv_path.open(encoding='utf-8',newline='') as f:csv_rows=list(csv.DictReader(f))
        assert sum(int(r['total_bytes']) for r in csv_rows)==expected_total
        assert any(r['application_path'].startswith("'=") for r in csv_rows)
        allowed={reader.current_sid(),'S-1-5-18','S-1-5-32-544'}
        for path in (json_path,csv_path):
            security=win32security.GetFileSecurity(str(path),win32security.DACL_SECURITY_INFORMATION)
            acl=security.GetSecurityDescriptorDacl()
            actual={win32security.ConvertSidToStringSid(acl.GetAce(i)[2]) for i in range(acl.GetAceCount())}
            assert actual==allowed,'Export ACL is not owner/SYSTEM/Administrators only'
        # Explicit refresh preserves a selected and focused existing row.
        page.locator('.fact-entry > summary').first.click();focused=page.locator('.fact-entry > summary').first
        focused.focus();selected=page.locator('.fact-entry[open]').first.get_attribute('data-fact-id')
        focused_id=focused.get_attribute('id');page.locator('#view-refresh').click();settled(page)
        assert page.locator('.fact-entry[open]').first.get_attribute('data-fact-id')==selected
        expect(page.locator('[id="'+focused_id+'"]')).to_be_focused()
        page.locator('#nav-3').click();settled(page)
        expect(page.get_by_text('synthetic-profile',exact=False).first).to_be_visible()
        expect(page.get_by_text('unavailable',exact=True).first).to_be_visible()
        page.screenshot(path=str(output/'policy.png'),full_page=True)
        page.locator('#nav-4').click();settled(page)
        page.screenshot(path=str(output/'health.png'),full_page=True)
        page.locator('#nav-2').click();settled(page)
        page.locator('#group-by').select_option('destination_ip');settled(page)
        page.locator('#saved-name').fill('Synthetic grouped destinations');page.locator('#save-query').click()
        expect(page.locator('#export-status')).to_contain_text('Saved locally')
        page.locator('#group-by').select_option('');settled(page)
        page.locator('#saved-select').select_option('Synthetic grouped destinations');page.locator('#open-query').click();settled(page)
        expect(page.locator('#group-by')).to_have_value('destination_ip')
        # A real nonexistent owner pipe provides an isolated source unavailable
        # state without stopping/updating the user's GlassWire service.
        missing=reader.PipeClient('missing-'+uuid.uuid4().hex);session.collector.reader=missing
        page.locator('#nav-5').click();settled(page)
        from validate_desktop_windows import set_recording
        set_recording(page,True)
        expect(page.locator('#autosave-status')).to_have_text('Settings save automatically')
        page.locator('#refresh').click();expect(page.locator('#autosave-status')).to_have_text('Settings save automatically')
        # Refresh acknowledges acquisition, not completion. Observe the source's
        # terminal state through its actual health projection; the five-second
        # health cadence must not race an assertion with the same deadline.
        page.wait_for_function("()=>document.querySelector('#traffic-status')?.textContent==='unavailable'",timeout=0)
        page.screenshot(path=str(output/'stale-source.png'),full_page=True)
        set_recording(page,False);expect(page.locator('#autosave-status')).to_have_text('Settings save automatically')
        missing.close()
        page.locator('#retention-days').fill('14');page.locator('#retention-days').press('Tab')
        expect(page.locator('#history-status')).to_contain_text('Local history updated')
        assert not errors,errors
        session.close();sessions.remove(session)
        reopened=NativeSession(shell,synthetic,playwright);sessions.append(reopened);page=reopened.page
        settled(page);page.locator('#nav-2').click();settled(page)
        page.locator('#saved-select').select_option('Synthetic application');page.locator('#open-query').click();settled(page)
        expect(page.locator('#fact-count')).to_have_text(str(scoped_count)+' facts')
        reopened.close();sessions.remove(reopened)

        # Accepted user amendment: actual native WebView2 zoom, NOT a CDP
        # viewport emulation or Windows-wide display/DPI setting change.
        zoomed=NativeSession(shell,synthetic,playwright,zoom=150);sessions.append(zoomed);page=zoomed.page
        settled(page);select_range(page,START,END)
        zoom_snapshot=snapshot(page)
        assert abs(zoom_snapshot['viewport']['device_pixel_ratio']-1.5)<0.01
        assert zoom_snapshot['layout']['document_width']<=zoom_snapshot['viewport']['width']
        skip=page.get_by_role('button',name='Skip to analytics content',exact=True)
        skip.focus();expect(skip).to_be_focused();skip.press('Enter')
        expect(page.locator('#analytics-main')).to_be_focused()
        page.locator('#nav-2').focus();page.locator('#nav-2').press('Enter');settled(page)
        page.locator('#filter-value').focus();expect(page.locator('#filter-value')).to_be_focused()
        page.locator('.fact-entry > summary').first.focus();page.locator('.fact-entry > summary').first.press('Enter')
        expect(page.locator('taild-evidence')).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(output/'activity-native-150-percent.png'),full_page=True)
        page.locator('#nav-0').click();settled(page)
        page.screenshot(path=str(output/'overview-native-150-percent.png'),full_page=True)
        page.locator('h1').scroll_into_view_if_needed()
        capture_preview(zoomed,output/'overview-native-150-percent-surface.png')
        page.locator('#dashboard-countries').scroll_into_view_if_needed()
        capture_preview(zoomed,output/'geography-native-150-percent-surface.png')
        reports.append(zoom_snapshot)
        zoomed.close();sessions.remove(zoomed)

        # Actual retained source -> current packaged UI -> scoped rows/export.
        actual=output/'real-history';history.private_directory(actual)
        with sqlite3.connect('file:'+str(real_history).replace('\\','/')+'?mode=ro',uri=True) as source,sqlite3.connect(actual/'history.sqlite3') as target:
            source.backup(target)
        with history_context(actual) as store:
            if policy_history:
                with sqlite3.connect('file:'+str(policy_history).replace('\\','/')+'?mode=ro',uri=True) as source:
                    for row in source.execute("SELECT data FROM snapshots WHERE kind='policy'"):
                        analytics.Analytics(store).record_policy(json.loads(row[0]))
            latest=store.db.execute('SELECT max(time) FROM traffic').fetchone()[0]
            live_end=history.utc(latest+1000000);live_start=history.utc(latest-300000000)
            expected=analytics.Analytics(store).batch([{'kind':'traffic','view':'summary','start':live_start,'end':live_end}])['results'][0]['data']['data']['total_bytes']
            policy_times=store.db.execute("SELECT min(time),max(time) FROM snapshots WHERE kind='policy'").fetchone()
        live=NativeSession(shell,actual,playwright);sessions.append(live);page=live.page
        settled(page);select_range(page,live_start,live_end)
        page.locator('#nav-1').click();settled(page)
        assert page.locator('#application-table .identity-link').count()>0
        page.locator('#application-table .identity-link').first.click();settled(page)
        page.get_by_role('button',name='Inspect application activity',exact=True).click();settled(page)
        # Wait for the feature's mounted row, not just the shell's busy flag.
        page.wait_for_function("()=>!!document.querySelector('.fact-entry')",timeout=0)
        expect(page.locator('.fact-entry').first).to_be_visible()
        page.locator('.fact-entry > summary').first.click()
        page.screenshot(path=str(output/'real-activity-evidence.png'),full_page=True)
        page.get_by_role('button',name='Remove application scope',exact=True).click();settled(page)
        actual_export=actual/'actual-evidence.json';export_ui(live,'json',actual_export)
        observed=json.loads(actual_export.read_text(encoding='utf-8'))
        actual_total=sum(int(r['total_bytes']) for r in observed['result']['data']['rows'])
        assert actual_total==expected
        actual_policy=False
        if policy_times[0] is not None:
            page.locator('#nav-3').click();settled(page)
            select_range(page,history.utc(policy_times[0]),history.utc(policy_times[1]+1))
            assert page.locator('.policy-snapshot').count()>0
            page.screenshot(path=str(output/'real-policy.png'),full_page=True)
            actual_policy=True
        live.close();sessions.remove(live)
        report={'state':'passed','actual_native_ui':True,'synthetic_exact_total_bytes':str(expected_total),
            'actual_retained_source_total_bytes':str(actual_total),'actual_source_row_count':observed['result']['data']['total_count'],
            'actual_event_drilldown':True,'same_revision_private_export':True,'native_save_dialog':True,'export_acl_verified':True,
            'compound_filters':True,'saved_scope_restart':True,'stable_pagination':True,'concurrent_revision_rejected':True,
            'literal_source_text':True,'formula_safe_csv':True,'physical_windows_150_percent_scaling':False,
            'native_app_local_zoom_percent':150,'zoom_css_viewport':zoom_snapshot['viewport'],
            'native_webview_capture_preview':True,'os_capture_used_for_zoom_acceptance':False,
            'zoom_keyboard_and_overflow_verified':True,'lazy_compact_candidate_evidence':True,
            'installed_client_changed':False,'snapshots':reports,'source_history_opened_read_only':True,'actual_policy_rendered':actual_policy,
            'dashboard_six_summaries':True,'dns_series_count_and_native_export':True,'clipped_dns_bin_scope':True,
            'country_focus_without_query':True,'source_context_navigation':True,'portmaster_layout_relationships':True,
            'provider_country_decisions_default_and_native_export':True,'inferred_traffic_mode_retained':True,'documented_outcome_widgets':True,
            'build_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [shell,shell.with_suffix('.dll'),*(shell.parent/'ui').glob('*.js'),*(shell.parent/'ui').glob('*.css')]}}
        (output/'analytics-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='snapshots'}))
    finally:
        for session in sessions:session.close()


class history_context:
    def __init__(self,directory):self.directory=directory
    def __enter__(self):self.store=history.History(self.directory,now=END);return self.store
    def __exit__(self,*_):self.store.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--real-history',required=True,type=Path);parser.add_argument('--policy-history',type=Path)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output,args.real_history.resolve(strict=True),args.policy_history)
