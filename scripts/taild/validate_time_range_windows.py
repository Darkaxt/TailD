"""Actual native seven-day preset/navigation/drill-down, isolated from installation."""
import argparse
import hashlib
import json
from pathlib import Path

from validate_analytics_windows import NativeSession,populate,settled,select_range,START,END
from validate_desktop_windows import snapshot


def run(shell,output):
    from playwright.sync_api import sync_playwright,expect
    output.mkdir(parents=True,exist_ok=False)
    home=output/'history';populate(home)
    with sync_playwright() as playwright:
        session=NativeSession(shell,home,playwright)
        try:
            page=session.page;settled(page)
            expect(page.locator('#time-range')).to_have_value('week')
            bounds=page.locator('#utc-start,#utc-end').evaluate_all('(nodes)=>nodes.map(n=>n.value)')
            assert page.evaluate('([a,b])=>Date.parse(b)-Date.parse(a)',bounds)==7*86400000
            expect(page.locator('#dns-card span')).to_have_text('125')
            labels=page.locator('#dashboard-dns-trend svg .tick text').all_text_contents()
            assert any('Oct ' in v for v in labels),labels
            first=snapshot(page)
            page.locator('#nav-1').click();settled(page)
            assert page.locator('#utc-start,#utc-end').evaluate_all('(nodes)=>nodes.map(n=>n.value)')==bounds
            page.locator('#nav-0').click();settled(page)
            old_end=page.locator('#utc-end').input_value()
            page.locator('#view-refresh').click();settled(page)
            assert page.locator('#utc-end').input_value()>old_end
            for preset,duration in [('recent',900000),('hour',3600000)]:
                page.locator('#time-range').select_option(preset);settled(page)
                observed=page.locator('#utc-start,#utc-end').evaluate_all('(nodes)=>nodes.map(n=>n.value)')
                assert page.evaluate('([a,b])=>Date.parse(b)-Date.parse(a)',observed)==duration
            select_range(page,START,END)
            page.locator('#view-refresh').click();settled(page)
            assert page.locator('#utc-start').input_value()==START
            assert page.locator('#utc-end').input_value()==END
            page.locator('#time-range').select_option('week');settled(page)
            page.locator('#dashboard-dns-trend details summary').click()
            rows=page.locator('#dashboard-dns-trend tbody tr')
            index=next(i for i,v in enumerate(rows.evaluate_all('(nodes)=>nodes.map(r=>Number(r.cells[1].textContent))')) if v)
            rows.nth(index).get_by_role('button').click();settled(page)
            expect(page.locator('#mode-dns')).to_have_attribute('aria-selected','true')
            expect(page.locator('#fact-count')).to_have_text('125 facts')
            expect(page.locator('#time-range')).to_have_value('custom')
            report={'ok':True,'native_served_url':page.url,'default':'week','rolling_hours':168,
                'shorter_presets':True,'navigation_preserves_bounds':True,'refresh_rolls_preset':True,
                'explicit_refresh_preserves_bounds':True,'seven_day_dns_count':125,'bin_drilldown':True,
                'multi_day_utc_labels':labels,'initial_render':first,'installed_client_changed':False,
                'assets_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (shell.parent/'ui').glob('*.js')}}
            (output/'time-range-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in report.items() if k not in ('initial_render','assets_sha256')}))
        finally:session.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output)
