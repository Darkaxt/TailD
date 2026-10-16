"""R31 native-served source-state/layout matrix; no installed-service changes."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from validate_analytics_windows import NativeSession,populate,settled,capture_preview


def run(shell,output):
    output.mkdir(parents=True,exist_ok=False);reports=[]
    with sync_playwright() as playwright:
        for zoom in (100,150):
            for mode in ('none','dns','traffic','both','retained'):
                root=output/(mode+'-'+str(zoom));root.mkdir()
                if mode=='retained':populate(root/'history')
                session=NativeSession(shell,root/'history',playwright,zoom=150 if zoom==150 else None)
                try:
                    session.collector.traffic_available=mode in ('traffic','both')
                    if mode in ('dns','both'):
                        session.collector.config['provider']={'account_scope':'fixture','endpoint':'fixture',
                            'account_type':'personal','instance':'europe'}
                        session.collector._transient_token='fixture-not-a-provider-token'
                    page=session.page;page.set_default_timeout(0);errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    settled(page);page.locator('#view-refresh').click();settled(page)
                    traffic=mode in ('traffic','both','retained');dns=mode in ('dns','both','retained')
                    assert page.locator('#dashboard-bandwidth').count()==int(traffic)
                    assert page.locator('#dashboard-consumers').count()==int(traffic)
                    assert page.locator('#dashboard-dns-trend').count()==int(dns)
                    assert page.locator('#dashboard-map').count()==int(dns)
                    assert page.locator('#nav-1').count()==int(traffic)
                    expect(page.locator('.source-availability-notice')).to_contain_text('Recording disabled')
                    for width in (None,560):
                        if width:page.set_viewport_size({'width':round(width*zoom/100),'height':round(800*zoom/100)})
                        layout=page.evaluate('''()=>({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,
                          cards:[...document.querySelectorAll('.dashboard-grid>*,.dashboard-column>*')].map(e=>{
                            const b=e.getBoundingClientRect();return {id:e.id,x:b.x,y:b.y,width:b.width,height:b.height}})})''')
                        assert not layout['overflow'],layout
                        assert all(card['width']>0 for card in layout['cards']),layout
                        if width:assert layout['width']==560,layout
                        capture_preview(session,root/('overview-'+str(width or 'native')+'.png'))
                        reports.append({'mode':mode,'zoom':zoom,'url':page.url,'traffic':traffic,'dns':dns,'layout':layout})
                    if mode=='none':
                        session.collector.traffic_available=True
                        page.wait_for_function("()=>!!document.querySelector('#dashboard-bandwidth')",timeout=0)
                        settled(page)
                        session.collector.traffic_available=False
                        page.wait_for_function("()=>!document.querySelector('#dashboard-bandwidth')",timeout=0)
                        settled(page)
                    assert not errors,errors
                finally:session.close()
    result={'ok':True,'reports':reports,'installed_services_unchanged':True}
    (output/'sources.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'ok':True,'layouts':len(reports),'installed_services_unchanged':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output.resolve())
