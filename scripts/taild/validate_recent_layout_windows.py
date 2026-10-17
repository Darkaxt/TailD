"""R34 real native WebView geometry, search and incident interaction regressions.

Uses real renderer/bridge/management/history; only provider and daemon boundaries
are fixtures. No installed client, real credentials or provider policy is changed.
"""
import argparse,copy,hashlib,json,threading
from contextlib import ExitStack
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright,expect
import connectivity,management
from test_connectivity import DaemonFixture
from test_management import snapshot
from validate_analytics_windows import NativeSession,capture_preview


def measure(page):
    return page.evaluate('''()=>{
      const rect=e=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height,bottom:b.bottom}};
      const list=document.querySelector('#management-recent .incident-table');
      return {viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},
        list:rect(list),panel:rect(document.querySelector('#management-recent')),
        scroll:{height:list.scrollHeight,client:list.clientHeight},
        decisions:[...document.querySelectorAll('#management-recent tbody .decision-heading')].slice(0,6).map(e=>({
          badge:rect(e.querySelector('.decision-badge')),actions:rect(e.querySelector('.decision-actions'))})),
        overflow:document.documentElement.scrollWidth>innerWidth,
        mainOverflow:getComputedStyle(document.querySelector('main')).overflowY};}''')


def resize(session,width,height):
    import win32con,win32gui,win32process
    windows=[]
    win32gui.EnumWindows(lambda w,_:windows.append(w) if win32process.GetWindowThreadProcessId(w)[1]==session.native.pid and win32gui.IsWindowVisible(w) else None,None)
    assert len(windows)==1,windows
    window=windows[0];outer=win32gui.GetWindowRect(window);client=win32gui.GetClientRect(window)
    before=session.page.evaluate('({width:innerWidth,height:innerHeight})')
    expected={'width':round(width*before['width']/client[2]),'height':round(height*before['height']/client[3])}
    win32gui.SetWindowPos(window,None,0,0,width+outer[2]-outer[0]-client[2],height+outer[3]-outer[1]-client[3],
                         win32con.SWP_NOMOVE|win32con.SWP_NOZORDER|win32con.SWP_NOACTIVATE)
    session.page.wait_for_function('(s)=>Math.abs(innerWidth-s.width)<=1&&Math.abs(innerHeight-s.height)<=1',arg=expected,timeout=0)


def ready(page):
    page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'",timeout=0)


def run(shell,output,diagnostic=False):
    output.mkdir(parents=True,exist_ok=False);reports=[]
    with sync_playwright() as playwright:
      for zoom in (100,150):
        root=output/str(zoom);root.mkdir();current=snapshot();writes=[];reads=[];fail_write=threading.Event();conflict=threading.Event()
        current['resources']['endpoints']['data']['devices'].append({'PK':'other','name':'Other endpoint','profile':{'PK':'profile'}})
        def provider_read(*a,**k):
            reads.append('read');value=copy.deepcopy(current)
            if conflict.is_set() and len(reads)%2==0:value['profile']='changed-profile'
            return value
        def provider_write(token,method,route,payload,org):
            if fail_write.is_set():raise management.ManagementError('management-outcome-unknown')
            writes.append({'method':method,'route':route,'payload':copy.deepcopy(payload)})
            rows=current['resources']['rules']['data']['rules'];name=payload['hostnames[]'][0]
            rows[:]=[r for r in rows if r['PK']!=name]+[{'PK':name,'comment':payload.get('comment',''),
                'action':{'do':payload['do'],'status':payload['status']}}]
        with ExitStack() as stack:
            stack.enter_context(patch('management.credentials.CredentialStore.__init__',return_value=None))
            stack.enter_context(patch('management.credentials.CredentialStore.read',return_value='synthetic'))
            stack.enter_context(patch('management.controld._body',side_effect=lambda path,*a:{'options':[]} if path=='/profiles/options' else {'PK':'account'}))
            stack.enter_context(patch('management.controld.policy_snapshot',side_effect=provider_read))
            stack.enter_context(patch('management.write',side_effect=provider_write))
            session=NativeSession(shell,root/'history',playwright,zoom=150 if zoom==150 else None,open_overview=False)
            try:
                page=session.page;page.set_default_timeout(0);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                session.collector.connectivity=connectivity.Connectivity(None,call=DaemonFixture())
                session.collector.command('configure',{'provider':{'account_scope':'local','endpoint':'device','account_type':'personal','instance':'europe'}})
                def seed():
                    now=datetime.now(timezone.utc)
                    for i in range(36):
                        session.collector.store.import_live_dns({'timestamp':(now-timedelta(seconds=i+1)).isoformat(),
                            'endpointId':'device','profileId':'profile','question':f'host-{i}.example','rrType':'A',
                            'action':('0','1','2','-1','99','3')[i%6],'trigger':'filter','triggerValue':'ads'},'local','device',collected=now.isoformat())
                    session.collector.store.import_live_dns({'timestamp':(now-timedelta(days=3)).isoformat(),
                        'endpointId':'device','profileId':'profile','question':'host-0.example','rrType':'A',
                        'action':'1'},'local','device',collected=now.isoformat())
                session.collector._commit(seed);page.locator('#nav-3').click();ready(page)
                page.get_by_label('Follow recent activity',exact=True).uncheck()
                expect(page.locator('#management-recent tbody tr')).to_have_count(36)
                expect(page.locator('#management-recent thead th')).to_have_text(['Time','Question','Decision / reason','First seen','Total'])
                expect(page.locator('#management-recent tbody tr').first.locator('td').last).to_have_text('2')
                expect(page.locator('#management-endpoint')).not_to_contain_text(' · device')
                expect(page.locator('#ingestion-notice')).to_have_count(0)
                for row in page.locator('#management-recent tbody tr').all():
                    expect(row.locator('td')).to_have_count(5)
                    icons=row.locator('.decision-heading button')
                    assert icons.count() in (2,3)
                    assert icons.evaluate_all('(buttons)=>buttons.every(b=>!b.textContent.trim()&&b.querySelector("svg")&&b.getAttribute("aria-label")&&b.title)')
                layouts=[]
                for width,height in ((1424,861),(1264,761),(1008,729),(1904,1041),(884,701),(784,561)):
                    resize(session,width,height);layout=measure(page);layouts.append(layout)
                    if diagnostic:continue
                    assert layout['list']['height']>=120,layout
                    assert layout['list']['height']<=max(220,layout['viewport']['height']),layout
                    assert layout['scroll']['height']>layout['scroll']['client'],layout
                    for decision in layout['decisions']:
                        badge,actions=decision['badge'],decision['actions']
                        assert actions['x']>=badge['x']+badge['width']+7,decision
                        assert abs((actions['y']+actions['height']/2)-(badge['y']+badge['height']/2))<1,decision
                    assert not layout['overflow'],layout
                    last=page.locator('#management-recent tbody tr').last
                    last.scroll_into_view_if_needed();expect(last).to_be_in_viewport()
                    page.locator('#incident-dns-search').scroll_into_view_if_needed()
                    expect(page.locator('#incident-dns-search')).to_be_in_viewport()
                resize(session,1424,861)
                page.locator('#incident-dns-search').scroll_into_view_if_needed()
                page.locator('#management-recent .incident-table').evaluate('e=>e.scrollTop=0')
                capture_preview(session,root/'restored.png')
                if diagnostic:
                    reports.append({'zoom':zoom,'layouts':layouts});continue
                for text,count in [('Blocked',6),('Allowed',6),('bYpAsS',6),('Redirected',12),('Request failed',6),('Unknown',6)]:
                    page.locator('#incident-dns-search').fill(text)
                    expect(page.locator('#management-recent tbody tr')).to_have_count(count)
                page.locator('#incident-dns-search').fill('no-matching-host')
                expect(page.locator('#management-recent .empty-state')).to_contain_text('No resolutions match')
                page.locator('#incident-dns-search').fill('host-0.example')
                row=page.locator('#management-recent tbody tr');expect(row).to_have_count(1)
                expect(row.get_by_role('button',name='Block',exact=True)).to_have_count(0)
                expect(row.get_by_role('button',name='Allow',exact=True)).to_have_count(1)
                expect(row.get_by_role('button',name='Allow',exact=True).locator('svg path')).to_have_attribute('d','m5 12 4 4L19 6')
                before=measure(page);row.get_by_role('button',name='Edit rule for host-0.example',exact=True).click()
                dialog=page.get_by_role('dialog',name='Edit policy rule',exact=True);expect(dialog).to_be_visible()
                expect(page.locator('#incident-hostname')).to_be_focused()
                after=measure(page);assert before['list']==after['list'],(before,after)
                capture_preview(session,root/'edit-floating.png');page.keyboard.press('Escape')
                expect(dialog).not_to_be_visible();expect(row.get_by_role('button',name='Edit rule for host-0.example',exact=True)).to_be_focused()
                expect(page.locator('#incident-dns-search')).to_have_value('host-0.example')
                before_reads=len(reads);row.get_by_role('button',name='Allow',exact=True).focus()
                row.get_by_role('button',name='Allow',exact=True).press('Enter');ready(page)
                expect(page.locator('.incident-workspace>.incident-notice')).to_contain_text('Bypass rule applied')
                assert len(writes)==1 and writes[-1]['payload']['do']==1,writes
                assert len(reads)>=before_reads+3,reads
                assert not page.locator('dialog[open]').count()
                expect(row.locator('.decision-badge')).to_have_text('Blocked')
                page.locator('#incident-dns-search').fill('host-1.example');expect(row).to_have_count(1)
                expect(row.get_by_role('button',name='Allow',exact=True)).to_have_count(0)
                expect(row.get_by_role('button',name='Block',exact=True).locator('svg circle')).to_have_count(1)
                row.get_by_role('button',name='Block',exact=True).click();ready(page)
                assert len(writes)==2 and writes[-1]['payload']['do']==0,writes
                row.get_by_role('button',name='Edit rule for host-1.example',exact=True).click()
                expect(dialog).to_be_visible();page.locator('#incident-comment').fill('Edited in floating dialog')
                page.locator('#incident-save-rule').click();ready(page)
                expect(dialog).not_to_be_visible()
                assert len(writes)==3 and writes[-1]['payload']['comment']=='Edited in floating dialog',writes
                fail_write.set();row.get_by_role('button',name='Block',exact=True).click();ready(page)
                expect(page.locator('.incident-workspace>.error')).to_contain_text('outcome could not be verified')
                assert len(writes)==3;fail_write.clear()
                # Rebind between the fresh prepare read and apply: never write.
                conflict.set();reads.clear();row.get_by_role('button',name='Block',exact=True).click();ready(page)
                expect(page.locator('.incident-workspace>.error')).to_contain_text('profile or its affected devices changed')
                assert len(writes)==3;conflict.clear()
                assert not errors,errors
                reports.append({'zoom':zoom,'url':page.url,'layouts':layouts,'writes':writes,'page_errors':errors,
                    'search_labels':True,'floating_edit':True,'direct_actions':True,'failure_conflict_no_retry':True})
            finally:session.close()
    assets={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (shell.parent/'ui').glob('*') if f.is_file()}
    report={'ok':not diagnostic,'diagnostic':diagnostic,'native_served':True,'assets':assets,'reports':reports}
    (output/'recent-layout.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--diagnostic',action='store_true');args=parser.parse_args()
    run(args.shell.resolve(strict=True),args.output.resolve(),args.diagnostic)
