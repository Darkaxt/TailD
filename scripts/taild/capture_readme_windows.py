"""Capture the actual native TailD UI with synthetic, publication-safe demo facts.

No provider requests, credentials, installed-client control or real history reads.
Requires the isolated Debug desktop host; output PNGs are intentional docs assets.
"""
import argparse,copy,hashlib,json
from datetime import datetime,timezone
from unittest.mock import patch
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
import analytics,history,connectivity
from test_connectivity import DaemonFixture
from test_management import snapshot as policy_fixture
from validate_analytics_windows import NativeSession,settled,select_range,capture_preview

START='2026-10-12T12:00:00Z'
END='2026-10-15T12:00:00Z'
APPLICATIONS=(
    (r'C:\Program Files\Mozilla Firefox\firefox.exe','US','198.51.100.2',7_000_000),
    (r'C:\Program Files\Google\Chrome\Application\chrome.exe','DE','198.51.100.3',4_500_000),
    (r'C:\Program Files (x86)\Steam\steam.exe','NL','198.51.100.4',9_500_000),
    (r'C:\Program Files\Microsoft VS Code\Code.exe','GB','198.51.100.5',1_800_000),
    (r'C:\Program Files\Discord\Discord.exe','FR','198.51.100.6',600_000),
    (r'C:\Program Files\Tailscale\tailscaled.exe','JP','198.51.100.7',120_000))


def populate_demo(directory):
    store=history.History(directory,now=END);traffic=[];decisions=[]
    start=history.instant(START)
    def decision(timestamp,question,code,answer='',country=None):
        raw={'timestamp':history.utc(timestamp),'endpointId':'demo-endpoint','profileId':'demo-profile',
            'question':question,'rrType':'A','action':code,'answers':answer,'trigger':'demo-rule' if code=='0' else '',
            'answerCountryCode':country or '','answerASN':'64500' if country else ''}
        decisions.append({'source':'controld-activity-csv','raw':raw})
    for hour in range(72):
        for app,(path,country,ip,base) in enumerate(APPLICATIONS):
            index=hour*len(APPLICATIONS)+app;timestamp=start+(hour*3600+app*43+2)*1000000
            incoming=base*(2+(hour*7+app)%9)//4;outgoing=base*(1+(hour+app)%5)//35
            traffic.append({'timestamp_utc':history.utc(timestamp),'timestamp_raw':timestamp//1000000,
                'application_id':app,'application_path':path,'destination_ip':ip,'destination_port':443,
                'protocol_raw':97,'flags_raw':0,'destination_status':'observed-ipv4-little-endian',
                'inbound_bytes':incoming,'outbound_bytes':outgoing,
                'provenance':{'rowid':index+1,'remote_host_blob_sha256':hashlib.sha256(ip.encode()).hexdigest(),
                    'application_blob_sha256':hashlib.sha256(path.encode()).hexdigest()}})
            decision(timestamp-1000000,('updates','cdn','downloads','api','chat','relay')[app]+'.example.com','1',ip,country)
            if index%3==0:decision(timestamp+1000000,'ads.example.net','0')
            if index%7==0:decision(timestamp+2000000,'media.example.org','2',ip,country)
            if index%11==0:decision(timestamp+3000000,'unavailable.example.net','-1')
            if index%41==0:decision(timestamp+4000000,'unknown.example.org','99')
    window={'start_inclusive':START,'end_exclusive':END}
    store.import_traffic({'source':'glasswire-sqlite-observed-v1','collected_at_utc':END,
        'generation':{'traffic_database':{'file_id':'public-demo-traffic'},'application_database':{'file_id':'public-demo-applications'}},
        'query_window':window,'truncated':False,'rows':traffic},'demo-workstation')
    store.import_dns({'source':'controld-activity-csv','collected_at_utc':END,'endpoint_id':'demo-endpoint',
        'query_window':window,'truncated':False,'rows':decisions},'demo-account','demo-endpoint')
    engine=analytics.Analytics(store)
    engine.record_context('demo-workstation',{'source':'taildns-cli-readonly','captured_at_utc':START,
        'observed_until_utc':END,'coverage_method':'observed-change-stream','backend_state':'Running',
        'node_id':'demo-node','user_id':'demo-user','resolver_endpoint':'demo-endpoint','dns_accepted':True,
        'local_override':True,'resolver_applied':True,'portal_mode':False,'endpoint_exclusivity':'unverified'})
    engine.record_policy({'source':'controld-api-readonly','account_scope':'demo-account','endpoint':'demo-endpoint',
        'profile':'demo-profile','captured_at_utc':END,'consistency':'separate-api-reads','historical_rule_causality':'not-established',
        'resources':{'rules':{'state':'available','route':'GET /profiles/demo-profile/rules/all',
            'data':{'rules':[{'PK':'ads.example.net','do':0}]}},
            'filters':{'state':'available','route':'GET /profiles/demo-profile/filters','data':{'filters':[{'name':'Demo privacy filter'}]}},
            'services':{'state':'available','route':'GET /profiles/demo-profile/services','data':{'services':[]}}}})
    store.close()
    return {'traffic_buckets':len(traffic),'dns_decisions':len(decisions),'applications':len(APPLICATIONS)}


def run(shell,scratch,output,zoom=100):
    if scratch.exists():raise ValueError('Use new, exact task-owned scratch')
    history.private_directory(scratch);counts=populate_demo(scratch/'history')
    output.mkdir(parents=True,exist_ok=True)
    names=('overview.png','geography.png','applications.png','activity.png','connection.png','resolver.png','management.png','policy.png')
    if any((output/name).exists() for name in names):raise ValueError('Refuse to replace existing screenshots without review')
    with sync_playwright() as playwright:
        session=NativeSession(shell,scratch/'history',playwright,zoom=zoom if zoom!=100 else None)
        try:
            page=session.page;page.set_viewport_size({'width':1440,'height':1000});settled(page);select_range(page,START,END)
            expect(page.locator('taild-world-map .map-surface')).to_have_attribute('data-map-ready','true')
            assert page.url=='https://taild.local/index.html'
            expect(page.locator('#dns-card span')).to_have_text(str(counts['dns_decisions']))
            page.locator('h1').scroll_into_view_if_needed();capture_preview(session,output/'overview.png')
            page.locator('#dashboard-countries').scroll_into_view_if_needed();capture_preview(session,output/'geography.png')
            page.locator('#nav-1').click();settled(page)
            expect(page.locator('#application-table tbody tr')).to_have_count(counts['applications'])
            page.locator('h1').scroll_into_view_if_needed();capture_preview(session,output/'applications.png')
            page.locator('#nav-2').click();settled(page)
            page.locator('.fact-entry > summary').first.click()
            expect(page.locator('taild-evidence')).to_have_count(1)
            page.locator('#activity-explorer').scroll_into_view_if_needed();capture_preview(session,output/'activity.png')
            daemon=DaemonFixture();daemon.profile['Name']='Demo account'
            daemon.status['Self']['HostName']='Demo workstation'
            session.collector.connectivity=connectivity.Connectivity(None,call=daemon)
            page.locator('#category-tailscale').click()
            page.wait_for_function("()=>document.querySelector('#connectivity-window')?.getAttribute('aria-busy')==='false'",timeout=0)
            page.locator('h1').scroll_into_view_if_needed();capture_preview(session,output/'connection.png')
            page.locator('#nav-resolver').click()
            expect(page.locator('#connectivity-resolver')).to_have_value('https://dns.example.invalid/test')
            capture_preview(session,output/'resolver.png')
            session.collector.command('configure',{'provider':{'account_scope':'demo-account','endpoint':'demo-endpoint',
                'account_type':'personal','instance':'acceptance'}})
            fixture=policy_fixture();fixture.update(endpoint='demo-endpoint',profile='demo-profile')
            fixture['resources']['profiles']['data']['profiles']=[{'PK':'demo-profile','name':'Demo privacy'}]
            fixture['resources']['endpoints']['data']['devices']=[{'PK':'demo-endpoint','name':'Demo workstation','profile':{'PK':'demo-profile'}},
                {'PK':'demo-tablet','name':'Demo tablet','profile':{'PK':'demo-profile'}}]
            fixture['resources']['filters']['data']['filters'][0]['name']='Ads & Trackers'
            fixture['resources']['rules']['data']['rules']=[{'PK':'ads.example.net','comment':'Demo incident',
                'action':{'do':0,'status':1}}]
            now=datetime.now(timezone.utc).isoformat()
            for question,action in (('ads.example.net','0'),('updates.example.com','1'),('media.example.org','3')):
                session.collector._commit(lambda question=question,action=action:session.collector.store.import_live_dns({
                    'timestamp':now,'endpointId':'demo-endpoint','profileId':'demo-profile','question':question,
                    'rrType':'A','action':action,'trigger':'filter' if action=='0' else '',
                    'triggerValue':'ads' if action=='0' else '', 'categories':[{'categoryName':'Technology'}]},
                    'demo-account','demo-endpoint',collected=now))
            with patch('management.credentials.CredentialStore.read',return_value='synthetic-publication-read'), \
                 patch('management.controld.policy_snapshot',side_effect=lambda *a,**k:copy.deepcopy(fixture)) as reads, \
                 patch('management.option_catalog',side_effect=lambda snapshot,*a:snapshot):
                page.locator('#nav-3').click()
                page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'",timeout=0)
                expect(page.locator('#management-recent tbody tr')).to_have_count(3)
                expect(page.locator('#management-recent')).to_contain_text('Ads & Trackers')
                page.locator('h1').scroll_into_view_if_needed();capture_preview(session,output/'management.png')
                # Actual native/pipe/backend revisit must not perform another provider read.
                page.locator('#category-tailscale').click();page.locator('#nav-3').click()
                page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'",timeout=0)
                expect(page.locator('#management-binding')).to_contain_text('Session policy snapshot')
                assert reads.call_count==1,reads.call_count
                refresh=page.get_by_role('button',name='Refresh DNS',exact=True)
                expect(refresh).to_have_text('');expect(refresh).to_have_attribute('title','Refresh DNS')
                refresh.focus();refresh.press('Enter')
                expect(refresh).to_be_enabled();expect(page.locator('#management-recent tbody tr')).to_have_count(3)
                icon=refresh.evaluate('e=>({width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height,svg:e.querySelector("svg").getAttribute("aria-hidden")})')
                assert icon['width']>=36 and icon['height']>=36 and icon['svg']=='true',icon
                page.locator('#nav-policy').click()
                expect(page.locator('#management-policy')).to_contain_text('ads.example.net')
                page.locator('h1').scroll_into_view_if_needed();capture_preview(session,output/'policy.png')
                page.locator('#management-reload').click()
                page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'",timeout=0)
                assert reads.call_count==2,reads.call_count
                page.locator('#nav-recent-dns').click()
                # Native ZoomFactor consumes physical WebView pixels at 150%.
                page.set_viewport_size({'width':round(560*zoom/100),'height':round(1000*zoom/100)})
                refresh.scroll_into_view_if_needed();expect(refresh).to_be_visible()
                narrow=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
                assert narrow['width']==560 and narrow['scroll']<=narrow['width'],narrow
                capture_preview(session,scratch/'narrow.png')
                assert reads.call_count==2
                assert daemon.writes==[]
            evidence={'synthetic_demo_only':True,'provider_requests':0,'installed_client_changed':False,
                'native_app_zoom':zoom,'capture_completed_at_utc':datetime.now(timezone.utc).isoformat(),
                'native_served_url':page.url,'documentation_viewport':{'width':1440,'height':1000},
                'narrow_css_width':560,'initial_policy_reads':1,'revisit_extra_policy_reads':0,'explicit_reload_reads':1,
                'refresh_icon':icon,'remote_policy_fixture_only':True,'keyboard_refresh_verified':True,
                'counts':counts,'assets_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (shell.parent/'ui').glob('*.js')},
                'screenshots_sha256':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in names}}
            (scratch/'capture-provenance.json').write_text(json.dumps(evidence,indent=2));print(json.dumps(evidence))
        finally:session.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--shell',type=Path,required=True)
    parser.add_argument('--scratch',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--zoom',type=int,choices=(100,150),default=100)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.scratch,args.output,args.zoom)
