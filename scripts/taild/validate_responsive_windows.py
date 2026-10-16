"""R32 native background-read/navigation and viewport acceptance; synthetic only."""
import argparse,copy,json,threading,time
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import analytics,connectivity
from test_connectivity import DaemonFixture
from test_management import snapshot as policy_fixture
from validate_analytics_windows import NativeSession,populate,settled,capture_preview

def run(shell,output):
    from playwright.sync_api import sync_playwright,expect
    output.mkdir(parents=True,exist_ok=False);reports=[]
    for zoom in (100,150):
        root=output/str(zoom);root.mkdir();populate(root/'history')
        daemon=DaemonFixture();daemon.status['Peer']['x'].update(Online=False,TaildropTarget=1,OS='linux')
        for name,presence,target in (('Enabled fixture',True,1),('Disabled fixture',True,4),('Unknown fixture',None,1)):
            peer=copy.deepcopy(daemon.status['Peer']['x'])
            peer.update(ID=name,HostName=name,Online=presence,TaildropTarget=target)
            daemon.status['Peer'][name]=peer
        entered=threading.Event();release=threading.Event();hold={'active':True};calls={'summary':0}
        original=analytics.Analytics._query
        def query(engine,request,revision,prepared=None):
            if request['kind']=='traffic' and request['view']=='summary':
                calls['summary']+=1
                if hold['active']:entered.set();release.wait()
            return original(engine,request,revision,prepared)
        with sync_playwright() as playwright,patch.object(analytics.Analytics,'_query',query),patch.object(connectivity.Connectivity,'_call',lambda self,*a:daemon(*a)):
            session=NativeSession(shell,root/'history',playwright,zoom=150 if zoom==150 else None,open_overview=False)
            try:
                page=session.page;page.set_default_timeout(0)
                expect(page.locator('h1')).to_have_text('Connection')
                expect(page.locator('#connection-devices')).not_to_contain_text('TailDrop · Offline')
                expect(page.locator('#connection-devices')).not_to_contain_text('TailDrop · Available')
                expect(page.locator('#connection-devices')).not_to_contain_text('Presence unknown')
                expect(page.locator('#connection-devices')).to_contain_text('TailDrop · Enabled')
                expect(page.locator('#connection-devices')).to_contain_text('TailDrop · Disabled')
                expect(page.locator('#connection-devices tr').filter(has_text='Unknown fixture').locator('.device-badges')).not_to_contain_text('TailDrop')
                capture_preview(session,root/'connection.png')
                entered.wait() # Original actual background query is held, never cancelled.
                origin=page.evaluate('performance.now()');page.locator('#nav-preferences').click()
                page.wait_for_function("()=>document.querySelector('#analytics-toggle')&&!document.querySelector('#analytics-toggle').disabled")
                preferences_ms=page.evaluate('performance.now()')-origin
                page.locator('#category-analytics').click()
                page.wait_for_function("()=>document.querySelector('#dashboard-dns-trend svg')&&document.querySelector('#view-progress')")
                assert page.locator('.analytics-results').get_attribute('inert') is None
                page.locator('#category-tailscale').click()
                hold['active']=False;release.set()
                page.wait_for_function("()=>document.querySelector('#connection-devices')")
                page.locator('#category-analytics').click();settled(page)
                expect(page.locator('#received-card span')).not_to_have_text('Loading…')
                assert calls['summary']==1,'Returning must reuse the completed background snapshot'
                for width,height in ((1920,1080),(1440,900),(560,800)):
                    page.set_viewport_size({'width':round(width*zoom/100),'height':round(height*zoom/100)})
                    layout=page.evaluate('''()=>{const r=id=>{const b=document.querySelector(id).getBoundingClientRect();return {x:b.x,width:b.width,right:b.right,y:b.y,bottom:b.bottom}};return {width:innerWidth,document:document.documentElement.scrollWidth,countries:r('#dashboard-countries'),map:r('#dashboard-map'),row:r('.dashboard-body')}}''')
                    if layout['document']>layout['width']:
                        layout['overflow_nodes']=page.evaluate('''()=>[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,30).map(e=>({tag:e.tagName,id:e.id,class:e.className,right:e.getBoundingClientRect().right,width:e.getBoundingClientRect().width,min:getComputedStyle(e).minWidth,overflow:getComputedStyle(e).overflow}))''')
                        (root/'overflow.json').write_text(json.dumps(layout,indent=2));page.screenshot(path=str(root/'overflow.png'),full_page=True)
                    assert layout['document']<=layout['width'],layout
                    assert abs(layout['map']['right']-layout['row']['right'])<2,layout
                    if width in (1920,1440):assert abs(layout['map']['width']-480)<2,layout
                    if width>850:assert abs(layout['map']['x']-layout['countries']['right']-16)<2,layout
                    if width==560:assert layout['map']['y']>=layout['countries']['bottom'],layout
                    reports.append({'zoom':zoom,'layout':layout,'preferences_during_held_read_ms':preferences_ms})
                page.set_viewport_size({'width':round(1440*zoom/100),'height':round(1000*zoom/100)})
                fixture=policy_fixture();fixture['resources']['rules']['data']['rules']=[{'PK':f'test-{i}.invalid','action':{'do':i%2,'status':1}} for i in range(80)]
                session.collector.command('configure',{'provider':{'account_scope':'local','endpoint':'device','account_type':'personal','instance':'acceptance'}})
                session.collector.management._read=lambda *a:copy.deepcopy(fixture)
                now=datetime.now(timezone.utc).isoformat()
                def record():
                    for i in range(80):session.collector.store.import_live_dns({'timestamp':now,'endpointId':'device','question':f'test-{i}.invalid','profileId':'profile','rrType':'A','action':str(i%2)},'local','device',collected=now)
                session.collector._commit(record)
                page.locator('#nav-3').click()
                page.wait_for_function("()=>document.querySelectorAll('#management-recent tbody tr').length===80")
                expect(page.locator('.decision-block').first).to_have_text('Blocked')
                expect(page.locator('.decision-allow').first).to_have_text('Allowed · Bypass')
                for policy in (False,True):
                    if policy:page.locator('#nav-policy').click()
                    page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'")
                    geometry=page.evaluate('''()=>{const q=s=>document.querySelector(s),r=e=>{const b=e.getBoundingClientRect();return {top:b.top,bottom:b.bottom,height:b.height}};const table=q('.incident-table');return {viewport:innerHeight,footer:r(q('footer')),panel:r(q('#management-policy')||q('#management-recent')),lastControl:r(q('.incident-workspace').lastElementChild),table:r(table),tableScroll:table.scrollHeight,tableClient:table.clientHeight,overflow:document.documentElement.scrollHeight>innerHeight+2}}''')
                    assert geometry['footer']['bottom']<=geometry['viewport']+2,geometry
                    assert geometry['lastControl']['bottom']>=geometry['footer']['top']-28,geometry
                    assert geometry['tableScroll']>geometry['tableClient'],geometry
                    assert not geometry['overflow'],geometry
                    capture_preview(session,root/('policy.png' if policy else 'recent.png'))
                    reports.append({'zoom':zoom,'policy':policy,'incident_geometry':geometry})
                fixture['resources']['rules']['data']['rules']=[]
                page.locator('#management-reload').click()
                page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'&&document.querySelectorAll('#management-policy tbody tr').length===0")
                expect(page.locator('#management-policy')).to_contain_text('No matching rules')
                capture_preview(session,root/'policy-empty.png')
                page.locator('#nav-recent-dns').click()
                page.locator('#incident-dns-search').fill('not-a-retained-question.invalid')
                expect(page.locator('#management-recent .empty-state')).to_be_visible()
                capture_preview(session,root/'recent-empty.png')
                reports.append({'zoom':zoom,'empty_policy_and_recent_states':True})
                page.locator('#category-analytics').click();settled(page)
                page.locator('#dashboard-map').scroll_into_view_if_needed();capture_preview(session,root/'geography.png')
            finally:release.set();session.close()
    (output/'responsive.json').write_text(json.dumps({'ok':True,'reports':reports},indent=2))
    print(json.dumps({'ok':True,'native_layouts':len(reports),'background_snapshot_reused':True}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output.resolve())
