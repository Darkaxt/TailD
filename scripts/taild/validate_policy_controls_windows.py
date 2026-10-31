"""R41 real native Angular/pipe/SQLite/policy workflow; isolated data and provider only."""
import argparse,copy,hashlib,json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import analytics,history,management
from test_management import snapshot as policy_fixture
from validate_analytics_windows import NativeSession,populate,settled,END
from validate_desktop_windows import snapshot

def resize(session,width,height):
    import ctypes
    import win32con,win32gui,win32process
    windows=[]
    win32gui.EnumWindows(lambda w,_:windows.append(w) if win32process.GetWindowThreadProcessId(w)[1]==session.native.pid and win32gui.IsWindowVisible(w) else None,None)
    assert len(windows)==1
    dpi=ctypes.WinDLL('user32',use_last_error=True).SetThreadDpiAwarenessContext
    dpi.argtypes=[ctypes.c_void_p];dpi.restype=ctypes.c_void_p
    prior=dpi(ctypes.c_void_p(-4))
    assert prior,'Cannot select physical-pixel coordinates for this test thread'
    try:win32gui.SetWindowPos(windows[0],None,0,0,width,height,win32con.SWP_NOMOVE|win32con.SWP_NOZORDER|win32con.SWP_NOACTIVATE)
    finally:dpi(prior)

def run(shell,output):
    from playwright.sync_api import sync_playwright,expect
    output.mkdir(parents=True,exist_ok=False);populate(output/'history')
    store=history.History(output/'history',now=END)
    try:
        row=store.db.execute('SELECT * FROM dns LIMIT 1').fetchone()
        columns=list(row.keys());identity=columns.index('identity')
        with store.transaction():
            store.db.executemany('INSERT INTO dns VALUES('+','.join('?' for _ in columns)+')',
                (tuple('native-large-'+str(i) if j==identity else row[j] for j in range(len(columns))) for i in range(100001)))
    finally:store.close()
    fixture=policy_fixture();fixture['resources']['endpoints']['data']['devices'].append({'PK':'second','name':'Second device','profile':{'PK':'profile'}})
    fixture['resources']['filters']['data']['filters']=[
        {'PK':'ads','name':'Ads & Trackers','description':'Block advertising and trackers.','status':1},
        {'PK':'adult','name':'Adult content','description':'Content category.','status':0},
        {'PK':'security','name':'Security','description':'Choose one protection level.','status':1,'action':{'lvl':'strict'},'levels':[{'name':'strict','title':'Strict'}]},
        {'PK':'unsupported','name':'Unreported state','status':99},
        *[{'PK':'category'+str(i),'name':'Category '+str(i),'description':'A retained provider category.','status':i%2} for i in range(24)]]
    fixture['resources']['services']['data']['services']=[
        {'PK':'blocked','name':'Blocked service','action':{'do':0,'status':1}},
        {'PK':'allowed','name':'Allowed service','action':{'do':1,'status':1}},
        {'PK':'disabled','name':'Disabled service','action':{'do':0,'status':0}}]
    fixture['resources']['options']['data']['options']=[
        {'PK':'on','title':'Enabled option','type':'toggle','value':1,'configured':True},
        {'PK':'off','title':'Disabled option','type':'toggle','value':0,'configured':True},
        {'PK':'default','title':'Default option','type':'toggle','value':None,'configured':False}]
    writes=[]
    def write(token,method,route,payload,org=None):
        writes.append({'route':route,'payload':payload})
        key=route.rsplit('/',1)[1]
        if '/filters/' in route:
            row=next(f for f in fixture['resources']['filters']['data']['filters'] if f['PK']==key or any(l['name']==key for l in f.get('levels',[])))
            row.update(status=payload['status'],action={'lvl':key})
        elif '/services/' in route:
            next(s for s in fixture['resources']['services']['data']['services'] if s['PK']==key)['action']=payload.copy()
        elif '/options/' in route:
            next(o for o in fixture['resources']['options']['data']['options'] if o['PK']==key)['value']=payload['status']
        else:raise AssertionError('Unexpected fixture mutation')
        return {}
    with sync_playwright() as playwright,patch.object(management,'write',side_effect=write):
        session=NativeSession(shell,output/'history',playwright)
        try:
            page=session.page;page.set_default_timeout(0)
            page.clock.set_fixed_time(datetime.fromisoformat(END.replace('Z','+00:00')))
            page.reload();page.locator('#category-analytics').click();settled(page)
            expect(page.locator('#time-range')).to_have_value('week')
            expect(page.locator('#dns-card span')).to_have_text('100126')
            expect(page.locator('#received-card span')).not_to_have_text('Unavailable')
            expect(page.locator('#view-refresh')).to_have_attribute('aria-label','Refresh view')
            assert page.locator('#view-refresh taild-refresh-icon svg').count()==1
            page.screenshot(path=str(output/'dashboard.png'))
            session.collector.command('configure',{'provider':{'account_scope':'local','endpoint':'device','account_type':'personal','instance':'acceptance'}})
            manager=session.collector.management
            manager._read=lambda endpoint,*args:dict(copy.deepcopy(fixture),endpoint=endpoint)
            manager._write_token=lambda *args:'synthetic-only'
            page.locator('#nav-3').click();page.locator('#nav-policy').click()
            idle=lambda:page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'",timeout=0)
            idle();page.get_by_role('button',name='Filters',exact=True).click()
            ads=page.locator('.filter-setting').filter(has_text='Ads & Trackers')
            expect(ads.locator('select')).to_have_count(0)
            expect(ads.get_by_role('checkbox')).to_have_count(0)
            expect(ads.get_by_role('img',name='Enabled',exact=True)).to_have_count(1)
            expect(ads.get_by_role('button',name='Disable',exact=True)).to_have_count(1)
            expect(ads.get_by_role('button',name='Enable',exact=True)).to_have_count(0)
            adult=page.locator('.filter-setting').filter(has_text='Adult content')
            expect(adult.get_by_role('checkbox')).to_have_count(0)
            expect(adult.get_by_role('img',name='Disabled',exact=True)).to_have_count(1)
            expect(adult.get_by_role('button',name='Enable',exact=True)).to_have_count(1)
            expect(page.locator('.filter-setting').filter(has_text='Unreported state').get_by_role('button')).to_be_disabled()
            security=page.locator('.filter-setting').filter(has_text='Choose one protection level.')
            expect(security.get_by_role('checkbox')).to_have_count(2)
            expect(security.get_by_role('checkbox',name='Security · Strict',exact=True)).to_be_checked()
            def apply():
                expect(page.locator('dialog[open] #management-preview')).to_be_visible()
                page.locator('#management-confirm').check();page.locator('#management-apply').click();idle()
                assert not page.locator('.incident-workspace>.error').count()
            ads.get_by_role('button',name='Disable',exact=True).click()
            expect(ads.get_by_role('img',name='Enabled',exact=True)).to_have_count(1)
            assert not writes,'Preparing a change must not bypass policy review'
            apply();expect(ads.get_by_role('img',name='Disabled',exact=True)).to_have_count(1)
            expect(ads.get_by_role('button',name='Enable',exact=True)).to_have_count(1)
            security.get_by_role('checkbox',name='Security · Security',exact=True).click()
            assert len(writes)==1 and not page.locator('dialog[open]').count(),'Selection alone must not prepare or write policy'
            expect(security).to_contain_text('Current: Strict')
            security.get_by_role('button',name='Apply level',exact=True).click();apply()
            expect(security.get_by_role('checkbox',name='Security · Security',exact=True)).to_be_checked()
            expect(security.get_by_role('checkbox',name='Security · Strict',exact=True)).not_to_be_checked()
            expect(security).to_contain_text('Current: Security')
            render=[]
            for width,height in ((1658,1320),(1280,900)):
                resize(session,width,height);page.evaluate('document.querySelector("main").scrollTop=0')
                page.wait_for_function('()=>document.documentElement.scrollWidth<=innerWidth',timeout=0)
                before=page.locator('#management-binding').bounding_box()
                assert page.locator('#management-binding').evaluate('(e)=>getComputedStyle(e).position')=='static'
                page.screenshot(path=str(output/('policy-'+str(width)+'.png')))
                scroll=page.evaluate('''()=>{
                  let e=document.querySelector('.filter-setting');
                  while(e&&!(e.scrollHeight>e.clientHeight+1&&['auto','scroll'].includes(getComputedStyle(e).overflowY)))e=e.parentElement;
                  e=e||document.scrollingElement;window.__r41Scroller=e;
                  const contains=e.contains(document.querySelector('#management-binding'));
                  e.scrollTop=e.scrollHeight/2;
                  return {contains,top:e.getBoundingClientRect().top};}''')
                page.wait_for_function('()=>window.__r41Scroller.scrollTop>0',timeout=0)
                delta=page.evaluate('window.__r41Scroller.scrollTop');after=page.locator('#management-binding').bounding_box()
                if scroll['contains']:assert abs(after['y']-(before['y']-delta))<2,'Endpoint header floats over the scrolled policy'
                else:assert abs(after['y']-before['y'])<2 and after['y']+after['height']<=scroll['top']+2
                page.screenshot(path=str(output/('policy-scrolled-'+str(width)+'.png')))
                render.append(snapshot(page));page.evaluate('window.__r41Scroller.scrollTop=0')
            page.evaluate('document.querySelector("main").scrollTop=0')
            page.get_by_role('button',name='Services',exact=True).click()
            blocked=page.locator('.incident-setting').filter(has_text='Blocked service')
            expect(blocked.get_by_role('button',name='Block',exact=True)).to_have_count(0)
            expect(blocked.get_by_role('button',name='Allow · Bypass',exact=True)).to_have_count(1)
            disabled=page.locator('.incident-setting').filter(has_text='Disabled service')
            expect(disabled.get_by_role('button',name='Disable',exact=True)).to_have_count(0)
            page.get_by_role('button',name='Profile Options',exact=True).click()
            enabled=page.locator('.incident-setting').filter(has_text='Enabled option')
            expect(enabled.get_by_role('checkbox')).to_have_count(0)
            expect(enabled.get_by_role('img',name='Enabled',exact=True)).to_have_count(1)
            enabled.get_by_role('button',name='Disable',exact=True).click();apply()
            expect(enabled.get_by_role('img',name='Disabled',exact=True)).to_have_count(1)
            expect(enabled.get_by_role('button',name='Enable',exact=True)).to_have_count(1)
            for scheme in ('light','dark'):
                page.emulate_media(color_scheme=scheme)
                assert page.locator('html').evaluate('(e)=>getComputedStyle(e).colorScheme')=='dark'
                expect(enabled.get_by_role('img',name='Disabled',exact=True)).to_have_count(1)
            report={'verified':True,'served_url':page.url,'large_default_week_dns_events':100126,
                'single_value_status_dot_and_opposite_button':True,'multi_value_selection_does_not_write':True,'multi_level_readback':True,'unknown_state_disabled':True,
                'guarded_fixture_writes':writes,'single_applicable_state_actions':True,'scroll_anchor_verified':True,
                'refresh_vector_rendered':True,'existing_dark_palette_preserved':True,'renderer':render,
                'production_policy_mutations':False,'installed_client_changed':False,
                'served_assets':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (shell.parent/'ui').iterdir() if p.is_file()}}
            (output/'validation.json').write_text(json.dumps(report,indent=2))
            print(json.dumps({k:v for k,v in report.items() if k not in ('renderer','served_assets')}))
        finally:session.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output)
