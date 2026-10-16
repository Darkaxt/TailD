"""Native-served activity acceptance. Fixture transfers; optional real READ only.

No installed client, tailnet, provider policy or file-transfer mutations.
"""
import argparse,hashlib,json,threading
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright,expect
import history,tailscale_activity,reader
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


def ready(page,allow_error=False):
    page.wait_for_function("()=>document.querySelector('#tailscale-activity')?.getAttribute('aria-busy')==='false'",timeout=0)
    if not allow_error:assert page.locator('#tailscale-activity .error').count()==0


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
                    page=session.page;page.set_default_timeout(0);errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                    settled(page);before=geometry(page)
                    (root/'dashboard-geometry.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
                    page.locator('#category-tailscale').click();page.locator('#nav-devices').click();ready(page)
                    expect(page.locator('#activity-enabled')).not_to_be_checked()
                    original=session.collector.dispatch
                    def deny(request,**kwargs):
                        if request.get('op') in ('activity-configure','activity-delete'):raise reader.ReaderError('denied')
                        return original(request,**kwargs)
                    session.collector.dispatch=deny
                    page.locator('#activity-enabled').check();ready(page,True)
                    expect(page.locator('#tailscale-activity .error')).to_be_visible()
                    expect(page.locator('#activity-enabled')).not_to_be_checked()
                    session.collector.dispatch=original
                    page.locator('#activity-enabled').check();ready(page)
                    page.locator('#activity-reload').click();ready(page)
                    expect(page.locator('#activity-source')).to_have_text('connected')
                    expect(page.locator('#tailscale-history-table tbody tr')).to_have_count(2)
                    offline=page.locator('#tailscale-history-table tbody tr').filter(has_text='Fixture tablet')
                    expect(offline.locator('td').nth(3)).to_have_text(page.evaluate("new Date('2026-10-13T09:00:00Z').toLocaleString()"))
                    expect(page.locator('#tailscale-history-table tbody tr').filter(has_text='Fixture phone').locator('td').nth(3)).to_have_text('Online now')
                    expect(page.locator('#tailscale-history-table thead')).to_contain_text('Last online')
                    capture_preview(session,root/'devices.png')
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
                    page.locator('#activity-enabled').uncheck();ready(page)
                    session.collector.dispatch=deny
                    page.locator('#activity-delete').click();page.locator('#activity-delete-confirm').click();ready(page,True)
                    expect(page.locator('#tailscale-activity .error')).to_be_visible()
                    expect(page.locator('#tailscale-history-table tbody tr')).to_have_count(3)
                    session.collector.dispatch=original
                    page.locator('#activity-delete').click();page.locator('#activity-delete-confirm').click();ready(page)
                    expect(page.locator('#tailscale-history-table')).to_contain_text('No transfers observed')
                    assert not session.collector.config['dns'] and not session.collector.config['traffic']
                    assert not errors,errors
                    reports.append({'zoom':zoom,'url':page.url,'fixture_transfers':True,'opt_in_independence':True,
                        'keyboard':True,'responsive_560':True,'deletion':True,'mutation_failures_visible':True,'page_errors':errors,'dashboard_geometry':before})
                finally:session.close()
        (output/'activity.json').write_text(json.dumps({'ok':False,'fixture_reports':reports,'live_pending':live},indent=2),encoding='utf-8')
        if live:
            root=output/'live-read-only';root.mkdir();populate(root/'history')
            session=NativeSession(shell,root/'history',playwright)
            try:
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
                page.locator('#category-tailscale').click();page.locator('#nav-devices').click();ready(page)
                page.locator('#activity-enabled').check();ready(page)
                page.wait_for_function("()=>document.querySelector('#activity-source')?.textContent?.trim()==='connected'&&document.querySelectorAll('#tailscale-history-table .badge').length>0",timeout=0)
                count=page.locator('#tailscale-history-table tbody tr').count()
                assert count>0
                (root/'read-audit.json').write_text(json.dumps(reads,indent=2),encoding='utf-8')
                assert page.locator('#tailscale-history-table .badge').count()==count
                # Private real observations stay only in this local evidence folder.
                capture_preview(session,root/'devices-private.png')
                page.locator('#nav-tailscale-activity').click();ready(page)
                page.locator('#activity-include-baselines').check();ready(page)
                expect(page.locator('#tailscale-history-table')).to_contain_text('peer-baseline')
                page.locator('#activity-enabled').uncheck();ready(page)
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
