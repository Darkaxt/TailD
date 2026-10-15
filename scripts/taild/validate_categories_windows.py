"""R24 actual native renderer -> owner pipe -> typed controls -> daemon fixture.

No installed client changes or live network writes. Uses the same control routes
as production, replacing only the external daemon boundary and provider reads.
"""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path

from playwright.sync_api import sync_playwright,expect
import connectivity
from test_connectivity import DaemonFixture
from test_management import snapshot as policy_fixture
from validate_analytics_windows import NativeSession,populate,settled,capture_preview


def controls_ready(page):
    page.wait_for_function("()=>document.querySelector('#connectivity-window')?.getAttribute('aria-busy')==='false'",timeout=0)


def categories_visible(page):
    for name in ('Tailscale','Control D','Analytics','About TailD'):
        expect(page.get_by_role('button',name=name,exact=True)).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    about=page.locator('#nav-about').bounding_box()
    assert about and about['y']>page.evaluate('innerHeight')-90,about


def run(shell,output):
    output.mkdir(parents=True,exist_ok=False);receipts=[]
    with sync_playwright() as playwright:
        for zoom in (100,150):
            directory=output/str(zoom);directory.mkdir();populate(directory/'history')
            daemon=DaemonFixture();session=NativeSession(shell,directory/'history',playwright,zoom=150 if zoom==150 else None)
            try:
                session.collector.connectivity=connectivity.Connectivity(None,call=daemon)
                session.collector.command('configure',{'provider':{'account_scope':'local','endpoint':'device','account_type':'personal','instance':'acceptance'}})
                policy=policy_fixture();policy['resources']['filters']['data']['filters'][0]['name']='Ads & Trackers'
                session.collector.management._read=lambda endpoint,*args:copy.deepcopy(policy)
                now=datetime.now(timezone.utc).isoformat()
                session.collector._commit(lambda:session.collector.store.import_live_dns({'timestamp':now,'endpointId':'device',
                    'question':'blocked-category-test.invalid','profileId':'profile','rrType':'A','action':'0','trigger':'filter','triggerValue':'ads'},'local','device',collected=now))
                page=session.page;page.set_default_timeout(0);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                settled(page);categories_visible(page)
                expect(page.locator('#category-pages button')).to_have_count(5)
                page.locator('#category-tailscale').focus();page.locator('#category-tailscale').press('Enter');settled(page);controls_ready(page)
                expect(page.locator('#category-pages button')).to_have_count(3)
                expect(page.locator('#nav-0')).to_have_count(0);expect(page.locator('#nav-policy')).to_have_count(0)
                expect(page.locator('#scope-account')).to_have_count(0)
                expect(page.locator('#connectivity-window')).to_contain_text('Test device')
                expect(page.locator('#connectivity-window')).to_contain_text('Test exit')
                assert not daemon.writes
                categories_visible(page);capture_preview(session,directory/'tailscale-connection.png')
                page.locator('#nav-preferences').click();settled(page);controls_ready(page)
                for action in ('use-dns','allow-incoming','use-subnets','auto-update','unattended'):
                    toggle=page.locator('#connectivity-'+action)
                    if toggle.is_checked():toggle.uncheck()
                    else:toggle.check()
                    controls_ready(page)
                    expect(page.locator('#connectivity-error')).to_have_count(0)
                assert len(daemon.writes)==5
                expect(page.locator('#connectivity-use-dns')).not_to_be_checked()
                capture_preview(session,directory/'tailscale-preferences.png')
                page.locator('#connectivity-reset').click()
                expect(page.locator('.connectivity-confirm')).to_be_visible();assert len(daemon.writes)==5
                expect(page.locator('#connectivity-confirm')).to_be_focused()
                page.locator('#connectivity-confirm').click();controls_ready(page)
                assert len(daemon.writes)==6 and daemon.prefs['CorpDNS'] is True
                page.locator('#nav-resolver').click();settled(page)
                field=page.locator('#connectivity-resolver');field.fill('https://dns.example.invalid/r24');field.press('Tab');controls_ready(page)
                assert daemon.resolver['Endpoint']=='https://dns.example.invalid/r24'
                expect(page.locator('#connectivity-window')).to_contain_text('Applied')
                capture_preview(session,directory/'tailscale-resolver.png')
                page.locator('#connectivity-resolver-disable').click();controls_ready(page)
                assert daemon.resolver['Configured'] is False
                # Failed/stale state cannot leave apparently editable controls.
                daemon.profile['ID']='profile-b';daemon.resolver['ProfileID']='profile-b'
                before=len(daemon.writes)
                page.locator('#nav-preferences').click();settled(page)
                page.locator('#connectivity-use-dns').uncheck();controls_ready(page)
                expect(page.locator('#connectivity-error')).to_contain_text('changed')
                expect(page.locator('#connectivity-use-dns')).to_have_count(0)
                assert len(daemon.writes)==before
                page.locator('#connectivity-reload').click();controls_ready(page)
                # Exit and disconnect controls have the same explicit route.
                page.locator('#nav-connection').click();settled(page)
                page.locator('#connectivity-exit').select_option('exit-a');controls_ready(page)
                assert daemon.prefs['ExitNodeID']=='exit-a'
                page.locator('#connectivity-exit-lan').check();controls_ready(page)
                page.locator('#connectivity-run-exit').check();controls_ready(page)
                assert set(daemon.prefs['AdvertiseRoutes'])=={'10.9.0.0/16','0.0.0.0/0','::/0'}
                page.locator('#connectivity-run-exit').uncheck();controls_ready(page)
                assert daemon.prefs['AdvertiseRoutes']==['10.9.0.0/16']
                page.locator('#connectivity-toggle').click()
                expect(page.locator('#connectivity-confirm')).to_be_focused()
                assert daemon.prefs['WantRunning'] is True
                page.locator('#connectivity-confirm').click();controls_ready(page)
                assert daemon.prefs['WantRunning'] is False
                page.locator('#connectivity-toggle').click();controls_ready(page)
                assert daemon.prefs['WantRunning'] is True
                # Provider category hides every Tailscale page, but not its root.
                page.locator('#nav-3').click();settled(page)
                page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'",timeout=0)
                expect(page.locator('#category-pages button')).to_have_count(2)
                expect(page.locator('#nav-preferences')).to_have_count(0)
                expect(page.locator('#management-policy')).to_have_count(0)
                expect(page.locator('#management-recent')).to_contain_text('blocked-category-test.invalid')
                expect(page.locator('#management-recent')).to_contain_text('Ads & Trackers')
                categories_visible(page);capture_preview(session,directory/'control-d-recent.png')
                page.locator('#management-recent').get_by_role('button',name='Edit rule',exact=True).click();settled(page)
                expect(page.locator('#nav-policy')).to_have_attribute('aria-current','page')
                expect(page.locator('#incident-hostname')).to_have_value('blocked-category-test.invalid')
                expect(page.locator('#management-recent')).to_have_count(0)
                for name in ('Rules','Filters','Services','Profile Options'):
                    page.get_by_role('button',name=name,exact=True).click()
                    expect(page.locator('.incident-tabs .active')).to_have_text(name)
                # About is independent of category and remains below its roots.
                page.locator('#nav-about').focus();page.locator('#nav-about').press('Enter');settled(page)
                expect(page.locator('#about-version')).to_have_text('1.105.0+10')
                expect(page.locator('#category-pages')).to_have_count(0)
                for root in ('#category-tailscale','#nav-3','#category-analytics'):
                    expect(page.locator(root)).to_have_attribute('aria-expanded','false')
                expect(page.locator('#about-panel')).to_contain_text('Independent')
                rejected=page.evaluate('''()=>new Promise(resolve=>{
                  const id=910002,receive=e=>{if(e.data.id!==id)return;chrome.webview.removeEventListener('message',receive);resolve(e.data)};
                  chrome.webview.addEventListener('message',receive);
                  chrome.webview.postMessage({id,op:'open-product-link',body:{target:'javascript:invalid'}});
                })''')
                assert rejected['ok'] is False and rejected['state']=='invalid-command',rejected
                categories_visible(page);capture_preview(session,directory/'about.png')
                page.locator('#category-analytics').click();settled(page)
                for index in (1,2,4,5,0):
                    page.locator('#nav-'+str(index)).click();settled(page)
                    expect(page.locator('#analytics-error')).to_have_count(0)
                if zoom==100:
                    page.set_viewport_size({'width':560,'height':800})
                    page.locator('#category-tailscale').click();settled(page);controls_ready(page)
                    page.locator('#nav-preferences').click();settled(page);categories_visible(page)
                    page.screenshot(path=str(directory/'preferences-560.png'))
                    page.locator('#nav-3').click();settled(page)
                    page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'",timeout=0)
                    categories_visible(page);page.screenshot(path=str(directory/'control-d-560.png'))
                assert not errors,errors
                receipts.append({'zoom':zoom,'url':page.url,'category_exclusivity':True,'persistent_roots_and_about':True,
                    'typed_pipe_readback':True,'stale_snapshot_refused':True,'incident_edit_preserved':True,
                    'keyboard_category_and_about':True,'unapproved_external_link_rejected':True,
                    'daemon_fixture_mutations':len(daemon.writes),'production_mutations':False,
                    'backend_state':daemon.prefs['WantRunning'],'page_errors':errors})
            finally:session.close()
    result={'ok':True,'views':receipts,'native_served':True,'isolated_external_boundaries':True}
    (output/'categories.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output.resolve())
