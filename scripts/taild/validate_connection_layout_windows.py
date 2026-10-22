"""Live inventory/preferences geometry and accessibility on actual native assets."""
import argparse,copy,json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from test_connectivity import DaemonFixture
from validate_analytics_windows import NativeSession,settled,capture_preview


def run(shell,output):
    output.mkdir(parents=True,exist_ok=False);reports=[]
    with sync_playwright() as playwright:
        for zoom in (100,150):
            root=output/str(zoom);root.mkdir()
            session=NativeSession(shell,root/'history',playwright,zoom=150 if zoom==150 else None)
            try:
                daemon=DaemonFixture();peer=daemon.status['Peer']['x']
                peer.update(UserID=1,OS='linux',TaildropTarget=1,PrimaryRoutes=['192.168.50.0/24'],
                    Tags=['tag:router'],CapMap={'https://tailscale.com/cap/ssh':[]},
                    Created='2026-01-01T00:00:00Z',KeyExpiry='2027-01-01T00:00:00Z')
                offline=copy.deepcopy(peer);offline.update(ID='phone',HostName='Test phone',OS='android',
                    Online=False,TailscaleIPs=['100.64.0.3'],TaildropTarget=5,
                    LastSeen='2026-10-15T10:00:00Z',NoFileSharingReason='Peer is offline',
                    ExitNodeOption=False,PrimaryRoutes=[],Tags=['tag:mobile'],CapMap={})
                daemon.status['Peer']['phone']=offline
                session.collector.connectivity.call=daemon
                page=session.page;page.set_default_timeout(0);settled(page)
                origin=page.evaluate('performance.now()');page.locator('#category-tailscale').click()
                page.wait_for_function("()=>document.querySelectorAll('#connection-devices tbody tr').length===3",timeout=0)
                elapsed=page.evaluate('performance.now()')-origin
                assert not session.collector.config['activity'],'Live inventory must not enable recording'
                expect(page.locator('#connection-devices')).to_contain_text('SSH advertised')
                native=page.evaluate('({width:innerWidth,height:innerHeight})')
                for width in (None,560):
                    if width:page.set_viewport_size({'width':round(width*zoom/100),'height':round(800*zoom/100)})
                    layout=page.evaluate('''()=>({width:innerWidth,document:document.documentElement.scrollWidth,
                      table:document.querySelector('#connection-devices').getBoundingClientRect().width,
                      scroller:document.querySelector('#connection-devices').parentElement.clientWidth})''')
                    assert layout['document']<=layout['width'],layout
                    page.locator('#connection-devices tbody tr').filter(has_text='Test exit').locator('.device-metadata summary').click()
                    expect(page.locator('#connection-devices')).to_contain_text('192.168.50.0/24')
                    page.locator('#connection-devices tbody tr').filter(has_text='Test exit').locator('.device-metadata summary').click()
                    reports.append({'zoom':zoom,'url':page.url,'layout':layout,'navigation_to_live_rows_ms':elapsed})
                    page.locator('#connection-devices').scroll_into_view_if_needed()
                    capture_preview(session,root/('devices-'+str(width or 'native')+'.png'))
                page.set_viewport_size({key:round(value*zoom/100) for key,value in native.items()})
                page.locator('h1').scroll_into_view_if_needed()
                page.screenshot(path=str(root/'connection-full.png'),full_page=True)
                origin=page.evaluate('performance.now()');page.locator('#nav-preferences').click()
                page.wait_for_function("()=>document.querySelector('#analytics-toggle')&&!document.querySelector('#analytics-toggle').disabled",timeout=0)
                reports[-1]['preferences_ready_ms']=page.evaluate('performance.now()')-origin
                page.locator('#analytics-toggle').focus();expect(page.locator('#analytics-toggle')).to_be_focused()
                page.screenshot(path=str(root/'preferences.png'),full_page=True)
                expect(page.locator('.preference-details')).not_to_have_attribute('open','')
                page.locator('#nav-resolver').click()
                page.wait_for_function("()=>document.querySelector('#connectivity-window')?.getAttribute('aria-busy')==='false'",timeout=0)
                expect(page.locator('.resolver-primary')).to_contain_text('Custom resolver applied')
                expect(page.locator('.resolver-editor')).not_to_have_attribute('open','')
                page.locator('.resolver-editor summary').click()
                expect(page.locator('#connectivity-resolver')).to_have_value('https://dns.example.invalid/test')
                page.screenshot(path=str(root/'resolver.png'),full_page=True)
                # Intended running state is not a successful connection.
                daemon.status['BackendState']='Starting';page.locator('#connectivity-reload').click()
                page.wait_for_function("()=>document.querySelector('#connectivity-window')?.getAttribute('aria-busy')==='false'",timeout=0)
                expect(page.locator('.connection-account')).to_contain_text('Starting')
                expect(page.locator('.connection-account')).not_to_contain_text('Connected')
                assert daemon.writes==[],daemon.writes
                reports[-1]['resolver_and_actual_connection_state']=True
            finally:session.close()
    (output/'connection.json').write_text(json.dumps({'ok':True,'reports':reports},indent=2),encoding='utf-8')
    print(json.dumps({'ok':True,'reports':reports}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output.resolve())
