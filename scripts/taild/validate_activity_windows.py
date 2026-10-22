"""Native-served activity acceptance. Fixture transfers; optional real READ only.

No installed client, tailnet, provider policy or file-transfer mutations.
"""
import argparse,hashlib,json,threading
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright,expect
import history,tailscale_activity,reader,connectivity
from test_connectivity import DaemonFixture
from validate_analytics_windows import NativeSession,populate,settled,capture_preview,END


class FixtureStream:
    current=None
    def __init__(self):self.stopped=threading.Event()
    def cancel(self):self.stopped.set()
    def online(self):
        self.status['Peer']['b']['Online']=True
        self.receive('snapshot','fixture-profile',(self.status,{},None))
    def run(self,receive,connected):
        FixtureStream.current=self;self.receive=receive
        self.status={'BackendState':'Running','Peer':{
            'a':{'ID':'fixture-phone','HostName':'Fixture phone','OS':'android','Online':True},
            'b':{'ID':'fixture-tablet','HostName':'Fixture tablet','OS':'android','Online':False,'LastSeen':'2026-10-13T09:00:00Z'}}}
        receive('snapshot','fixture-profile',(self.status,
            {'Configured':True,'Applied':True,'CaptivePortal':False},{'Warnings':None}))
        receive('notify','fixture-profile',{'OutgoingFiles':[
            {'ID':'completed','Name':r'C:\private\Fixture sent.txt','PeerID':'fixture-phone','Started':END,
             'DeclaredSize':1024,'Sent':1024,'Finished':True,'Succeeded':True},
            {'ID':'failed','Name':'Fixture failed.txt','PeerID':'fixture-tablet','Started':END,
             'DeclaredSize':2048,'Sent':128,'Finished':True,'Succeeded':False}],
            'IncomingFiles':[{'Name':'Fixture received.txt','Started':END,'DeclaredSize':512,'Received':512,'Done':True}]})
        connected();self.stopped.wait()


class UnavailableReader:
    def discover(self,*args,**kwargs):raise reader.ReaderError('source-unavailable')


def recording(page,enabled):
    page.locator('#category-tailscale').click();page.locator('#nav-preferences').click()
    page.wait_for_function("()=>document.querySelector('#analytics-toggle')&&!document.querySelector('#analytics-toggle').disabled",timeout=0)
    page.locator('#analytics-toggle').set_checked(enabled)
    page.wait_for_function("()=>document.querySelector('#analytics-toggle')&&!document.querySelector('#analytics-toggle').disabled",timeout=0)


def ready(page,allow_error=False):
    page.wait_for_function("()=>document.querySelector('#tailscale-activity')?.getAttribute('aria-busy')==='false'",timeout=0)
    if not allow_error:
        error=page.locator('#tailscale-activity .error')
        assert error.count()==0,error.inner_text() if error.count() else ''


def geometry(page):
    return page.evaluate('''()=>Object.fromEntries([...document.querySelectorAll('.dashboard-grid>*,#dashboard-bandwidth .line-surface,#dashboard-bandwidth svg')].map((e,i)=>{
      const b=e.getBoundingClientRect();return [e.id||e.tagName+'-'+i,{x:b.x,y:b.y,width:b.width,height:b.height,bottom:b.bottom}]}))''')


def run(shell,output,live=False,live_only=False):
    output.mkdir(parents=True,exist_ok=False);reports=[]
    with sync_playwright() as playwright:
        for zoom in (() if live_only else (100,150)):
            root=output/str(zoom);root.mkdir();populate(root/'history')
            with patch.object(tailscale_activity,'Stream',FixtureStream):
                session=NativeSession(shell,root/'history',playwright,zoom=150 if zoom==150 else None)
                try:
                    session.collector.reader=UnavailableReader()
                    daemon=DaemonFixture()
                    daemon.status['Peer']={
                        'a':{'ID':'fixture-phone','HostName':'Fixture phone','OS':'android','Online':True,'TaildropTarget':1,
                            'UserID':1,'TailscaleIPs':['100.64.0.2'],'DNSName':'phone.fixture.invalid.',
                            'Tags':['tag:mobile'],'Created':'2026-01-01T00:00:00Z'},
                        'b':{'ID':'fixture-tablet','HostName':'Fixture tablet','OS':'linux','Online':False,'TaildropTarget':5,
                            'LastSeen':'2026-10-13T09:00:00Z','UserID':1,'TailscaleIPs':['100.64.0.3'],
                            'DNSName':'tablet.fixture.invalid.','ExitNodeOption':True,'PrimaryRoutes':['192.168.50.0/24'],
                            'CapMap':{'https://tailscale.com/cap/ssh':[]},'KeyExpiry':'2027-01-01T00:00:00Z',
                            'NoFileSharingReason':'Peer is offline'}}
                    session.collector.connectivity.call=daemon
                    page=session.page;page.set_default_timeout(0);errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                    # Match this retained-history fixture's owner clock. Wall time
                    # must not move its requested start beyond the fixture end.
                    page.clock.set_fixed_time(datetime.fromisoformat(END.replace('Z','+00:00')))
                    settled(page);before=geometry(page)
                    (root/'dashboard-geometry.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
                    page.locator('#category-tailscale').click()
                    page.wait_for_function("()=>document.querySelectorAll('#connection-devices tbody tr').length===3",timeout=0)
                    assert page.locator('#nav-devices').count()==0
                    expect(page.locator('#connection-devices')).to_contain_text('TailDrop')
                    recording(page,False)
                    expect(page.locator('#analytics-toggle')).not_to_be_checked()
                    original=session.collector.dispatch
                    def deny(request,**kwargs):
                        if request.get('op') in ('analytics-configure','activity-delete'):raise reader.ReaderError('denied')
                        return original(request,**kwargs)
                    session.collector.dispatch=deny
                    recording(page,True)
                    expect(page.locator('taild-analytics-preference .error')).to_be_visible()
                    expect(page.locator('#analytics-toggle')).not_to_be_checked()
                    session.collector.dispatch=original
                    recording(page,True)
                    page.locator('#nav-tailscale-activity').click();ready(page)
                    page.locator('#activity-reload').click();ready(page)
                    expect(page.locator('#activity-source')).to_have_text('connected')
                    page.locator('#nav-connection').click()
                    page.wait_for_function("()=>document.querySelectorAll('#connection-devices tbody tr').length===3",timeout=0)
                    offline=page.locator('#connection-devices tbody tr').filter(has_text='Fixture tablet')
                    expect(offline.locator('time')).to_have_attribute('title',page.evaluate("new Date('2026-10-13T09:00:00Z').toLocaleString()"))
                    expect(page.locator('#connection-devices tbody tr').filter(has_text='Fixture phone').locator('time')).to_contain_text('Online now')
                    expect(page.locator('#connection-devices thead')).to_contain_text('Last online')
                    expect(page.locator('#connection-devices')).to_contain_text('test@example.invalid')
                    expect(page.locator('#connection-devices')).to_contain_text('100.64.0.3')
                    expect(offline).to_contain_text('SSH advertised')
                    page.locator('#device-search').fill('100.64.0.3')
                    expect(page.locator('#connection-devices tbody tr')).to_have_count(1)
                    page.locator('#device-search').fill('')
                    page.locator('#connection-devices').scroll_into_view_if_needed()
                    capture_preview(session,root/'devices.png')
                    page.screenshot(path=str(root/'connection-full.png'),full_page=True)
                    page.locator('#nav-tailscale-activity').click();ready(page)
                    expect(page.locator('#tailscale-history-table')).to_contain_text('No changes recorded')
                    page.locator('#activity-include-baselines').check();ready(page)
                    expect(page.locator('#tailscale-history-table')).to_contain_text('peer-baseline')
                    expect(page.locator('#tailscale-history-table')).to_contain_text('already offline in starting snapshot')
                    page.locator('#activity-include-baselines').uncheck();ready(page)
                    expect(page.locator('#tailscale-history-table')).to_contain_text('No changes recorded')
                    FixtureStream.current.online()
                    page.locator('#activity-reload').click();ready(page)
                    expect(page.locator('#tailscale-history-table')).to_contain_text('peer-presence')
                    expect(page.locator('#tailscale-history-table')).not_to_contain_text('peer-baseline')
                    capture_preview(session,root/'activity.png')
                    page.locator('#nav-taildrop').click();ready(page)
                    expect(page.locator('#tailscale-history-table tbody tr')).to_have_count(3)
                    expect(page.locator('#tailscale-history-table')).to_contain_text('Received by daemon')
                    expect(page.locator('#tailscale-history-table')).to_contain_text('Failed')
                    assert 'C:' not in page.locator('#tailscale-history-table').inner_text()
                    expect(page.locator('#taildrop-open-downloads')).to_be_visible()
                    if zoom==100:
                        page.evaluate("""()=>{window.__taildropReplies=[];window.chrome.webview.addEventListener('message',e=>{
                          if(e.data?.data?.opened===true)window.__taildropReplies.push(e.data)});} """)
                        page.locator('#taildrop-open-downloads').click()
                        page.wait_for_function('()=>window.__taildropReplies.length===1',timeout=0)
                        assert page.evaluate('window.__taildropReplies[0].ok===true')
                    capture_preview(session,root/'taildrop.png')
                    page.locator('#tailscale-history-search').fill('failed');page.locator('#activity-reload').click();ready(page)
                    expect(page.locator('#tailscale-history-table tbody tr')).to_have_count(3)
                    page.locator('#tailscale-history-search').press('Enter');ready(page)
                    expect(page.locator('#tailscale-history-table tbody tr')).to_have_count(1)
                    page.locator('#tailscale-history-search').fill('');page.locator('#tailscale-history-search').press('Enter');ready(page)
                    page.locator('#activity-profile').select_option('fixture-profile');ready(page)
                    page.locator('#activity-reload').focus();page.keyboard.press('Enter');ready(page)
                    assert page.locator('#activity-reload').evaluate('e=>document.activeElement===e')
                    native=page.evaluate('({width:innerWidth,height:innerHeight})')
                    page.set_viewport_size({'width':round(560*zoom/100),'height':round(800*zoom/100)})
                    assert page.evaluate('innerWidth===560&&document.documentElement.scrollWidth<=innerWidth')
                    capture_preview(session,root/'taildrop-560.png')
                    page.set_viewport_size({key:round(value*zoom/100) for key,value in native.items()})
                    page.locator('#category-analytics').click();page.locator('#nav-5').click()
                    page.wait_for_function("()=>document.querySelector('#collection-window')?.getAttribute('aria-busy')==='false'",timeout=0)
                    expect(page.locator('#activity-status').locator('..')).to_contain_text('Tailscale activity')
                    page.locator('#category-tailscale').click();page.locator('#nav-taildrop').click();ready(page)
                    recording(page,False)
                    page.locator('#nav-taildrop').click();ready(page)
                    session.collector.dispatch=deny
                    page.locator('#activity-delete').click();page.locator('#activity-delete-confirm').click();ready(page,True)
                    expect(page.locator('#tailscale-activity .error')).to_be_visible()
                    expect(page.locator('#tailscale-history-table tbody tr')).to_have_count(3)
                    session.collector.dispatch=original
                    page.locator('#activity-delete').click();page.locator('#activity-delete-confirm').click();ready(page)
                    expect(page.locator('#tailscale-history-table')).to_contain_text('No transfers observed')
                    assert not session.collector.config['dns'] and not session.collector.config['traffic']
                    assert not errors,errors
                    reports.append({'zoom':zoom,'url':page.url,'fixture_transfers':True,'unified_recording_preference':True,
                        'keyboard':True,'responsive_560':True,'deletion':True,'mutation_failures_visible':True,'page_errors':errors,'dashboard_geometry':before})
                finally:session.close()
        (output/'activity.json').write_text(json.dumps({'ok':False,'fixture_reports':reports,'live_pending':live},indent=2),encoding='utf-8')
        if live:
            root=output/'live-read-only';root.mkdir();populate(root/'history')
            session=NativeSession(shell,root/'history',playwright)
            try:
                session.collector.reader=UnavailableReader()
                session.collector.connectivity=connectivity.Connectivity(Path('C:/Program Files/Tailscale/tailscale.exe'))
                session.collector.now=lambda:datetime.now(timezone.utc).isoformat()
                reads=[];original=session.collector.dispatch
                def audited(request,**kwargs):
                    result=original(request,**kwargs)
                    if request.get('op')=='activity-read':
                        reads.append({'requested_end':request.get('body',{}).get('end'),'server_now':session.collector.now(),
                            'rows':len(result['rows']),'source':result['source']['state'],'view':request.get('body',{}).get('view')})
                    return result
                session.collector.dispatch=audited
                page=session.page;page.set_default_timeout(0);settled(page)
                page.locator('#category-tailscale').click()
                page.wait_for_function("()=>document.querySelectorAll('#connection-devices tbody tr').length>0",timeout=0)
                count=page.locator('#connection-devices tbody tr').count()
                assert count>0
                (root/'read-audit.json').write_text(json.dumps(reads,indent=2),encoding='utf-8')
                assert page.locator('#connection-devices .badge').count()>=count
                # Private real observations stay only in this local evidence folder.
                capture_preview(session,root/'devices-private.png')
                recording(page,True)
                page.locator('#nav-tailscale-activity').click();ready(page)
                page.wait_for_function("()=>document.querySelector('#activity-source')?.textContent?.trim()==='connected'",timeout=0)
                page.locator('#activity-include-baselines').check();ready(page)
                expect(page.locator('#tailscale-history-table')).to_contain_text('peer-baseline')
                recording(page,False)
                reports.append({'real_read_only':True,'watch_connected':True,'native_visible_peer_rows':count,
                    'history_quick_check':session.collector._commit(lambda:session.collector.store.db.execute('PRAGMA quick_check').fetchone()[0]),
                    'no_device_or_policy_or_transfer_mutation':True})
            finally:session.close()
    result={'ok':True,'reports':reports,'installed_client_unchanged':True,
        'assets_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (shell.parent/'ui').glob('*.js')},
        'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__).with_name('runtime.py'),Path(__file__).with_name('tailscale_activity.py'))}}
    (output/'activity.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--live-read-only',action='store_true');parser.add_argument('--live-only',action='store_true')
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output.resolve(),args.live_read_only or args.live_only,args.live_only)
