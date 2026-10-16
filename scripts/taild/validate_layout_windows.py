"""R29 compact dashboard geometry on the actual native-served assets."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright
from validate_analytics_windows import NativeSession,populate,settled,capture_preview


def measure(page):
    return page.evaluate('''()=>{
      const rect=e=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height,bottom:b.bottom}};
      const columns=[...document.querySelectorAll('.dashboard-column')].map(c=>[...c.children].map(e=>({id:e.id,...rect(e)})));
      const bandwidth=document.querySelector('#dashboard-bandwidth'),chart=bandwidth?.querySelector('sfng-netquery-line-chart');
      const surface=bandwidth?.querySelector('.line-surface'),svg=surface?.querySelector('svg');
      return {columns,bandwidth:rect(bandwidth),chart:rect(chart),surface:rect(surface),svg:rect(svg),
        viewport:{width:innerWidth,height:innerHeight},overflow:document.documentElement.scrollWidth>innerWidth};}''')


def run(shell,output):
    output.mkdir(parents=True,exist_ok=False);reports=[]
    with sync_playwright() as playwright:
        for empty in (False,True):
          for zoom in (100,150):
            root=output/(('empty' if empty else 'populated')+'-'+str(zoom));root.mkdir()
            if not empty:populate(root/'history')
            session=NativeSession(shell,root/'history',playwright,zoom=150 if zoom==150 else None)
            try:
                page=session.page;page.set_default_timeout(0);settled(page);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                sizes=[None,560]
                for width in sizes:
                    if width:page.set_viewport_size({'width':round(width*zoom/100),'height':round(800*zoom/100)})
                    layout=measure(page)
                    if width:assert layout['viewport']['width']==width,layout
                    assert len(layout['columns'])==2,'Missing independently flowing body columns'
                    assert not layout['overflow'],layout
                    for column in layout['columns']:
                        for a,b in zip(column,column[1:]):assert abs(b['y']-a['bottom']-16)<1,(a,b)
                    assert layout['bandwidth']['bottom']-layout['chart']['bottom']<=17,layout
                    assert abs(layout['svg']['width']-layout['surface']['width'])<1,layout
                    assert abs(layout['svg']['height']-layout['surface']['height'])<1,layout
                    if empty:
                        chart=page.locator('#dashboard-bandwidth .chart-empty')
                        assert chart.count()==1
                        inside=chart.evaluate('e=>{const b=e.getBoundingClientRect(),s=e.parentElement.getBoundingClientRect();return b.top>=s.top&&b.bottom<=s.bottom&&b.left>=s.left&&b.right<=s.right}')
                        assert inside
                    page.locator('#dashboard-map').scroll_into_view_if_needed();capture_preview(session,root/('geography-'+str(width or 'native')+'.png'))
                    page.locator('#dashboard-bandwidth').scroll_into_view_if_needed();capture_preview(session,root/('bandwidth-'+str(width or 'native')+'.png'))
                    reports.append({'empty':empty,'zoom':zoom,'url':page.url,'layout':layout})
                assert not errors,errors
            finally:session.close()
    result={'ok':True,'reports':reports};(output/'layout.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({'ok':True,'layouts':len(reports)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output.resolve())
