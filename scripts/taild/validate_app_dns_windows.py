"""Native Windows app diagnosis acceptance; isolated history, no provider writes.

An optional real trace JSON supplies actual captured Windows process observations.
Policy outcomes are deterministic fixtures and are never described as live blocks.
"""
import argparse
import copy
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import uuid

import app_dns
import history
from validate_analytics_windows import NativeSession,capture_preview
from validate_recent_layout_windows import resize
from validate_desktop_windows import snapshot


def run(shell,output,real_trace=None):
    from playwright.sync_api import sync_playwright,expect
    output.mkdir(parents=True,exist_ok=False);reports=[]
    for zoom in (100,150):
      with sync_playwright() as playwright:
        root=output/str(zoom);root.mkdir()
        session=NativeSession(shell,root/'history',playwright,zoom=None if zoom==100 else zoom,open_overview=False)
        try:
            collector=session.collector;now=datetime.now(timezone.utc);collector.now=lambda:datetime.now(timezone.utc).isoformat()
            page=session.page;page.set_default_timeout(0);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            captured=[]
            if real_trace:captured=json.loads(real_trace.read_text(encoding='utf-8'))['events']
            def seed():
                collector.config['provider']={'account_scope':'fixture-account','endpoint':'fixture-device','account_type':'personal','instance':'europe'}
                facts=[]
                for i,name in enumerate(('blocked.example','allowed.example','unknown.example')):
                    at=history.instant((now-timedelta(seconds=30-i)).isoformat())
                    fact={'at':at,'question':name,'sequence':i+1,'type':1,'status':9003 if i!=1 else 0,'results':'',
                        'source':'windows-dns-client-3008','process':{'pid':234,'created':134370000000000000,'path':r'C:\Fixture\Example.exe'},
                        'binding':{'endpoint':'fixture-device','at':now.isoformat(),'method':'active-resolver-point-observation-after-batch'}}
                    facts.append(fact)
                    if i<2:
                        collector.store.import_live_dns({'timestamp':history.utc(at),'endpointId':'fixture-device','profileId':'fixture-profile',
                            'question':name,'rrType':'A','action':str(i),'trigger':'fixture-filter'},'fixture-account','fixture-device',collected=now.isoformat())
                app_dns.import_batch(collector.store,{'session':str(uuid.uuid4()),'events':facts},'local-windows')
                if captured:app_dns.import_batch(collector.store,{'session':str(uuid.uuid4()),'events':captured},'local-windows')
                collector.sources['app_dns']={'state':'observing','unassigned':0,'lost':0,'errors':0}
            collector._commit(seed)
            page.locator('#category-analytics').click();page.locator('#nav-app-domains').click()
            ready=lambda:page.wait_for_function("()=>document.querySelector('#app-dns-workspace')?.getAttribute('aria-busy')==='false'",timeout=0)
            ready();resize(session,1280,720)
            expect(page.locator('#app-dns-apps')).to_contain_text('Example.exe')
            expect(page.locator('#app-dns-apps')).to_contain_text('0 B')
            capture_preview(session,root/'applications.png')
            if captured:
                label=captured[0]['process']['path'].split('\\')[-1]
                page.get_by_role('button',name='Diagnose '+label,exact=True).click();ready()
                expect(page.locator('#app-dns-domains')).to_contain_text('example.com')
                capture_preview(session,root/'actual-windows-dns.png')
                page.get_by_role('button',name='Back to applications',exact=True).click();ready()
            page.get_by_role('button',name='Diagnose Example.exe',exact=True).click();ready()
            table=page.locator('#app-dns-domains')
            expect(table).to_contain_text('blocked.example');expect(table).to_contain_text('Blocked')
            page.get_by_role('button',name='Blocked',exact=True).click()
            expect(table).not_to_contain_text('allowed.example')
            page.get_by_role('button',name='Unknown',exact=True).click()
            expect(table).to_contain_text('unknown.example');expect(table).not_to_contain_text('blocked.example')
            page.get_by_role('button',name='All',exact=True).click()
            page.get_by_role('textbox',name='Search app domains',exact=True).fill('allowed')
            expect(table).to_contain_text('allowed.example');expect(table).not_to_contain_text('blocked.example')
            page.get_by_role('textbox',name='Search app domains',exact=True).fill('')
            page.get_by_role('button',name='blocked.example',exact=True).click()
            expect(table).to_contain_text('Resolution failed · 9003')
            page.get_by_role('button',name='blocked.example',exact=True).click()
            page.keyboard.press('Control+Home')
            capture_preview(session,root/'diagnosis.png')
            geometry=page.evaluate('''()=>{const t=document.querySelector('#app-dns-domains').getBoundingClientRect();return {viewport:{width:innerWidth,height:innerHeight},table:{top:t.top,bottom:t.bottom},overflow:document.documentElement.scrollWidth>innerWidth}}''')
            assert geometry['table']['top']<geometry['viewport']['height']-48,geometry
            assert not geometry['overflow'],geometry
            request={'start':(now-timedelta(days=1)).isoformat(),'end':(now+timedelta(seconds=1)).isoformat(),'path':r'C:\Fixture\Example.exe'}
            displayed=collector.dispatch({'op':'app-dns-read','body':request})
            exported=collector.dispatch({'op':'app-dns-export','body':{**request,'revision':displayed['revision'],'format':'json'}})
            content=json.loads(exported['content'])
            assert len(content['apps'])==1 and content['selected']['name']=='Example.exe'
            assert len(content['observations'])==3
            assert all(e['process']['path']==request['path'] for e in content['observations'])
            assert not errors,errors
            report={'zoom':zoom,'geometry':geometry,'renderer':snapshot(page),'page_errors':errors,
                'real_source_events':len(captured),'provider_decisions':'isolated fixtures only',
                'export_sha256':hashlib.sha256(exported['content'].encode()).hexdigest()}
            (root/'acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8');reports.append(report)
        finally:session.close()
    summary={'ok':True,'native_served':True,'reports':reports}
    (output/'acceptance.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({'ok':True,'zooms':[r['zoom'] for r in reports],'actual_source':bool(real_trace)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--real-trace',type=Path)
    args=parser.parse_args();run(args.shell,args.output,args.real_trace)
