"""Capture the actual native TailD UI with synthetic, publication-safe demo facts.

No provider requests, credentials, installed-client control or real history reads.
Requires the isolated Debug desktop host; output PNGs are intentional docs assets.
"""
import argparse,hashlib,json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
import analytics,history
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


def run(shell,scratch,output):
    if scratch.exists():raise ValueError('Use new, exact task-owned scratch')
    history.private_directory(scratch);counts=populate_demo(scratch/'history')
    output.mkdir(parents=True,exist_ok=True)
    names=('overview.png','geography.png','applications.png','activity.png')
    if any((output/name).exists() for name in names):raise ValueError('Refuse to replace existing screenshots without review')
    with sync_playwright() as playwright:
        session=NativeSession(shell,scratch/'history',playwright)
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
            evidence={'synthetic_demo_only':True,'provider_requests':0,'installed_client_changed':False,
                'native_served_url':page.url,'viewport':page.evaluate('({width:innerWidth,height:innerHeight})'),
                'counts':counts,'assets_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (shell.parent/'ui').glob('*.js')},
                'screenshots_sha256':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in names}}
            (scratch/'capture-provenance.json').write_text(json.dumps(evidence,indent=2));print(json.dumps(evidence))
        finally:session.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--shell',type=Path,required=True)
    parser.add_argument('--scratch',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.scratch,args.output)
