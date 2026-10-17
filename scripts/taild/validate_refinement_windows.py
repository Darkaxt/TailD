"""R36 complete native device/preferences and terminal history-read acceptance.

Only the owned validation host and synthetic collector are operated. No installed
client, production history, credentials, browser login or provider is changed.
"""
import argparse,json,sqlite3,threading
from pathlib import Path
from unittest.mock import patch
import analytics,connectivity
from test_connectivity import DaemonFixture
from validate_analytics_windows import NativeSession,populate,settled,capture_preview
from validate_recent_layout_windows import resize


def run(shell,output):
    from playwright.sync_api import sync_playwright,expect
    output.mkdir(parents=True,exist_ok=False);reports=[]
    with sync_playwright() as playwright:
      for zoom in (100,150):
        root=output/str(zoom);root.mkdir();populate(root/'history')
        release=threading.Event();entered=threading.Event();failure={'active':True,'calls':0}
        original=analytics.Analytics._query
        def query(engine,request,revision,prepared=None):
            if request['kind']=='traffic' and request['view']=='summary' and failure['active']:
                failure['calls']+=1;entered.set();release.wait()
                error=sqlite3.DatabaseError('synthetic private path must remain private')
                error.sqlite_errorcode=sqlite3.SQLITE_CORRUPT;raise error
            result=original(engine,request,revision,prepared)
            # Each frame fits the unchanged 16 MiB cap; the duplicate final batch
            # would exceed it. Exercise the actual native bridge, not a browser mock.
            result['data']['validation_padding']='x'*4_000_000
            return result
        with patch.object(analytics.Analytics,'_query',query):
          session=NativeSession(shell,root/'history',playwright,zoom=150 if zoom==150 else None,open_overview=False)
          try:
            page=session.page;page.set_default_timeout(0);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            daemon=DaemonFixture();daemon.status['Self'].update(UserID=1,OS='windows')
            daemon.status['Peer']['x'].update(OS='linux',Online=False,LastSeen='2026-10-14T12:00:00Z')
            session.collector.connectivity=connectivity.Connectivity(None,call=daemon)
            # Let the initial live read finish, then refresh from our daemon fixture.
            page.wait_for_function("()=>document.querySelector('#connectivity-reload')&&!document.querySelector('#connectivity-reload').disabled",timeout=0)
            page.locator('#connectivity-reload').click()
            page.wait_for_function("()=>document.querySelectorAll('#connection-devices tbody tr').length===2",timeout=0)
            expect(page.locator('#connection-devices thead th')).to_have_text(['Device / capabilities','Addresses','Last online'])
            expect(page.locator('#connection-devices tbody tr').first).to_contain_text('Test device')
            expect(page.locator('#connection-devices tbody tr').first.locator('.device-os')).to_have_attribute('aria-label','Windows')
            expect(page.locator('#connection-devices tbody tr').first.locator('.presence-square')).to_have_attribute('aria-label','Online')
            expect(page.locator('#connection-devices tbody tr').last.locator('time')).to_have_attribute('title',__import__('re').compile('2026'))
            expect(page.locator('#connectivity-toggle')).to_be_checked()
            page.locator('#connectivity-toggle').click()
            expect(page.get_by_role('heading',name='Disconnect this device?')).to_be_visible()
            expect(page.locator('#connectivity-toggle')).to_be_checked()
            page.get_by_role('button',name='Cancel',exact=True).click();assert not daemon.writes
            expect(page.locator('#nav-admin')).to_be_visible()
            assert not page.get_by_role('heading',name='This device',exact=True).count()
            assert not page.locator('#connectivity-exit').count()
            layouts=[]
            for width,height in ((1424,861),(1264,761),(1008,729),(784,561)):
                resize(session,width,height)
                geometry=page.evaluate('''()=>({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,
                  identity:document.querySelector('.device-identity').getBoundingClientRect().width})''')
                assert not geometry['overflow'],geometry;layouts.append(geometry)
            resize(session,1424,861);capture_preview(session,root/'connection.png')
            page.locator('#nav-preferences').click()
            page.wait_for_function("()=>document.querySelector('#analytics-toggle')&&!document.querySelector('#analytics-toggle').disabled",timeout=0)
            expect(page.locator('#analytics-toggle').locator('xpath=ancestor::app-dashboard-widget')).to_have_count(1)
            expect(page.locator('#connectivity-exit')).to_have_count(0)
            page.locator('#connectivity-use-exit').check();expect(page.locator('#connectivity-exit')).to_be_visible()
            expect(page.locator('#connectivity-exit-lan')).to_have_count(0)
            page.locator('#connectivity-exit').select_option('exit-a')
            page.wait_for_function("()=>!document.querySelector('#connectivity-exit-lan')?.disabled",timeout=0)
            assert daemon.prefs['ExitNodeID']=='exit-a'
            page.locator('#connectivity-use-exit').uncheck()
            page.wait_for_function("()=>document.querySelector('#connectivity-window')?.getAttribute('aria-busy')==='false'",timeout=0)
            expect(page.locator('#connectivity-exit')).to_have_count(0)
            expect(page.locator('#connectivity-exit-lan')).to_have_count(0)
            assert daemon.prefs['ExitNodeID']==''
            capture_preview(session,root/'preferences.png')
            # Background Overview keeps its original query across category changes.
            entered.wait();assert failure['calls']==1
            page.locator('#nav-3').click();page.locator('#category-analytics').click()
            assert failure['calls']==1,'Navigation duplicated the original background operation'
            release.set()
            page.wait_for_function("()=>document.querySelector('main')?.getAttribute('aria-busy')==='false'&&document.querySelector('#analytics-error')",timeout=0)
            expect(page.locator('#analytics-error')).to_contain_text('malformed database')
            expect(page.locator('#analytics-error')).not_to_contain_text('private path')
            expect(page.locator('#received-card span')).to_have_text('Unavailable')
            expect(page.locator('#dns-card span')).to_have_text('125')
            expect(page.locator('#view-loading')).to_have_count(0)
            assert failure['calls']==1,'Navigation duplicated the original background operation'
            capture_preview(session,root/'history-error.png')
            failure['active']=False
            page.locator('#category-tailscale').click();page.locator('#category-analytics').click();settled(page)
            expect(page.locator('#received-card span')).not_to_have_text('Unavailable')
            expect(page.locator('#received-card span')).not_to_have_text('Loading…')
            page.locator('#nav-about').click();expect(page.locator('#ingestion-notice')).to_have_count(1)
            assert not errors,errors
            reports.append({'zoom':zoom,'url':page.url,'layouts':layouts,'background_error_and_explicit_recovery':True,
                            'large_streamed_batch_ready':True,'specific_sanitized_history_error':True,'completed_dns_preserved':True,'source_notice_in_about':True})
          finally:release.set();session.close()
    result={'ok':True,'reports':reports,'installed_client_changed':False}
    (output/'refinement.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output.resolve())
