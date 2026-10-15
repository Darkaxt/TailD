"""R22 native-served branding, navigation and responsive layout acceptance.

Synthetic history and provider fixtures only. No installed-client changes,
provider requests, policy writes, or credential reads.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from playwright.sync_api import sync_playwright,expect
from test_management import snapshot as policy_fixture
from validate_analytics_windows import NativeSession,populate,settled,capture_preview


def artwork(page):
    return page.locator('taild-brand-mark').evaluate_all('''nodes=>nodes.map(e=>{
      const r=e.getBoundingClientRect(),s=e.querySelector('svg'),b=s?.getBBox();
      return {brand:e.dataset.brand,hidden:e.getAttribute('aria-hidden'),
        width:r.width,height:r.height,viewBox:s?.getAttribute('viewBox'),
        geometry:b?{width:b.width,height:b.height}:null,fill:s?getComputedStyle(s).fill:null};
    })''')


def assert_artwork(page):
    nodes=artwork(page)
    assert nodes and {n['brand'] for n in nodes}=={'tailscale','controld'}
    for node in nodes:
        assert node['hidden']=='true' and node['width']>=14 and node['height']>=14,node
        assert node['geometry']['width']>0 and node['geometry']['height']>0,node
        assert node['viewBox']==('0 0 26 26' if node['brand']=='tailscale' else '0 0 44 33'),node
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Horizontal page overflow'
    assert page.locator('#category-tailscale').inner_text()==''
    assert page.locator('#category-tailscale circle').count()==9
    expect(page.get_by_role('button',name='Control D',exact=True)).to_have_count(1)
    expect(page.locator('#nav-3 taild-brand-mark')).to_have_attribute('data-brand','controld')
    rail=page.locator('#nav-3').bounding_box();mark=page.locator('#nav-3 taild-brand-mark').bounding_box()
    # Chromium reports fractional CSS coordinates at native 150% zoom.
    assert rail and mark and math.isclose(rail['width'],40,abs_tol=.01) and math.isclose(mark['width'],22,abs_tol=.01),{'rail':rail,'mark':mark,
        'css':page.locator('#nav-3').evaluate('e=>({rail:getComputedStyle(e).width,mark:getComputedStyle(e.firstElementChild).width,dpr:devicePixelRatio})')}
    assert rail['x']<=mark['x'] and mark['x']+mark['width']<=rail['x']+rail['width']
    return nodes


def contrast(colors):
    def luminance(value):
        channels=[int(c)/255 for c in value.removeprefix('rgb(').removesuffix(')').split(',')]
        return sum(weight*(c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4)
                   for c,weight in zip(channels,(.2126,.7152,.0722)))
    low,high=sorted((luminance(colors['fg']),luminance(colors['bg'])))
    return (high+.05)/(low+.05)


def run(shell,output):
    output.mkdir(parents=True,exist_ok=False)
    reports=[]
    with sync_playwright() as playwright:
        for zoom in (100,150):
            directory=output/str(zoom);directory.mkdir();populate(directory/'history')
            session=NativeSession(shell,directory/'history',playwright,zoom=150 if zoom==150 else None)
            try:
                page=session.page;page.set_default_timeout(0);errors=[];requests=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.on('request',lambda request:requests.append(request.url))
                settled(page)
                assert page.url=='https://taild.local/index.html',page.url
                session.collector.command('configure',{'provider':{'account_scope':'local','endpoint':'device',
                    'account_type':'personal','instance':'acceptance'}})
                session.collector.management._read=lambda endpoint,*args:copy.deepcopy(policy_fixture())
                nodes=assert_artwork(page)
                capture_preview(session,directory/'overview.png')
                for index,title in enumerate(('Overview','Applications','Activity','Control D','Sources & health','Settings')):
                    if title=='Control D':page.locator('#nav-3').click();settled(page)
                    else:
                        page.locator('#category-analytics').click();settled(page)
                        page.locator('#nav-'+str(index)).click();settled(page)
                    expect(page.locator('#nav-recent-dns' if title=='Control D' else '#nav-'+str(index))).to_have_attribute('aria-current','page')
                    expect(page.locator('.page-heading h1')).to_have_text('Recent DNS' if title=='Control D' else 'Collection settings' if title=='Settings' else title)
                    if title=='Control D':
                        page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'")
                        expect(page.locator('.incident-binding h2')).to_have_text('Shared')
                        expect(page.locator('.section-title taild-brand-mark')).to_have_attribute('data-brand','controld')
                        expect(page.locator('.incident-workspace app-dashboard-widget>h2 taild-brand-mark')).to_have_count(2)
                        page.locator('#nav-policy').click();settled(page)
                        for tab in ('Rules','Filters','Services','Profile Options'):
                            page.get_by_role('button',name=tab,exact=True).click()
                            expect(page.locator('.incident-tabs button.active')).to_have_text(tab)
                        page.locator('#nav-recent-dns').click();settled(page);nodes=assert_artwork(page)
                        colors=page.locator('#nav-3').evaluate('e=>({fg:getComputedStyle(e).color,bg:getComputedStyle(e).backgroundColor})')
                        assert contrast(colors)>=3,colors
                        capture_preview(session,directory/'control-d.png')
                    if title=='Settings':
                        expect(page.locator('#collection-window .product-brand taild-brand-mark')).to_have_attribute('data-brand','tailscale')
                        expect(page.locator('#collection-window app-dashboard-widget>h2 taild-brand-mark')).to_have_count(1)
                # Native zoom is app-local, not Windows display scaling. Emulated
                # CSS viewport checks are separate from the native zoom capture.
                if zoom==100:
                    page.set_viewport_size({'width':560,'height':800})
                    page.locator('#nav-3').click();settled(page)
                    page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'")
                    assert_artwork(page)
                    page.screenshot(path=str(directory/'control-d-560.png'))
                    page.locator('#category-analytics').click();settled(page);assert_artwork(page)
                    page.screenshot(path=str(directory/'overview-560.png'))
                assert not errors,errors
                requests+=page.evaluate("performance.getEntriesByType('resource').map(e=>e.name)")
                assert all(url.startswith('https://taild.local/') for url in requests),requests
                reports.append({'zoom':zoom,'url':page.url,'native_pid':session.native.pid,
                    'marks':nodes,'active_provider_colors':colors,'active_provider_contrast':contrast(colors),'page_errors':errors,
                    'remote_requests':False,'navigation_pages':6,'profile_tabs':4,
                    'viewport':page.evaluate('({width:innerWidth,height:innerHeight})')})
            finally:session.close()
    receipt={'ok':True,'synthetic_only':True,'installed_client_unchanged':True,
        'shell_sha256':hashlib.sha256(shell.read_bytes()).hexdigest(),'views':reports}
    (output/'branding.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({'ok':True,'native_served':True,'zoom':[100,150],'narrow_css_width':560,'remote_requests':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    run(args.shell.resolve(strict=True),args.output.resolve())
