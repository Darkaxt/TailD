"""R44 real native Recent DNS over representative synthetic retained history.

Uses the existing Debug-only native validation bridge and a local fixture policy;
never opens production history, credentials, provider network or device state.
"""
import argparse,copy,hashlib,json,threading,time
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
import controld,history
from test_management import snapshot as policy_fixture
from validate_analytics_windows import NativeSession,END
from validate_desktop_windows import snapshot


def run(shell,output):
    from playwright.sync_api import sync_playwright,expect
    output.mkdir(parents=True,exist_ok=False)
    now=datetime.fromisoformat(END.replace('Z','+00:00'))
    store=history.History(output/'history',now=END)
    try:
        store.import_live_dns({'timestamp':(now-timedelta(seconds=1)).isoformat(),
            'endpointId':'device','question':'retained.invalid','rrType':'A','action':'0','profileId':'profile'},
            'local','device',collected=END)
        base=dict(store.db.execute('SELECT * FROM dns').fetchone())
        with store.transaction():
            def rows():
                for number in range(170704):
                    stamp=history.instant(END)-(number+2)*1000000 if number<124 else history.instant(END)-86400000000-number
                    raw=json.loads(base['data']);raw['raw']['timestamp']=history.utc(stamp)
                    yield (base['source'],str(number),0,stamp,'device','retained.invalid',base['revision'],history.packed(raw))
            store.db.executemany('INSERT INTO dns VALUES(?,?,?,?,?,?,?,?)',rows())
        store._source('traffic','unrelated-host')
    finally:store.close()
    release=threading.Event();entered=threading.Event();fixture=policy_fixture()
    def policy(endpoint,*args):
        entered.set();release.wait()
        return dict(copy.deepcopy(fixture),endpoint=endpoint)
    with sync_playwright() as playwright,patch.object(controld,'utc_now',return_value=now):
        session=NativeSession(shell,output/'history',playwright,open_overview=False)
        try:
            session.collector.command('configure',{'provider':{'account_scope':'local','endpoint':'device',
                'account_type':'personal','instance':'acceptance'}})
            session.collector.management._read=policy
            page=session.page;page.set_default_timeout(0);page.clock.set_fixed_time(now)
            measured=time.perf_counter();page.locator('#nav-3').click();entered.wait()
            page.wait_for_function("()=>document.querySelector('#management-recent .recent-content')?.getAttribute('aria-busy')==='false' && document.querySelectorAll('#management-recent tbody tr').length===100",timeout=0)
            seconds=time.perf_counter()-measured
            assert not release.is_set(),'DNS unexpectedly depended on policy completion'
            rows=page.locator('#management-recent tbody tr');expect(rows).to_have_count(100)
            expect(rows.first).to_contain_text('retained.invalid')
            assert all(text.strip()=='170705' for text in rows.locator('td:last-child').all_text_contents())
            assert page.locator('#recent-loading').count()==0
            assert not page.locator('#management-recent .error').count()
            release.set()
            page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'",timeout=0)
            page.locator('#incident-dns-search').fill('no-match.invalid')
            page.wait_for_function("()=>document.querySelector('#management-recent .recent-content')?.getAttribute('aria-busy')==='false' && document.querySelectorAll('#management-recent tbody tr').length===0",timeout=0)
            measured_refresh=time.perf_counter();page.locator('#incident-dns-search').fill('Blocked')
            page.wait_for_function("()=>document.querySelector('#management-recent .recent-content')?.getAttribute('aria-busy')==='false' && document.querySelectorAll('#management-recent tbody tr').length===100",timeout=0)
            refresh_seconds=time.perf_counter()-measured_refresh
            report={'verified':True,'served_url':page.url,'retained_decisions':170705,'visible_rows':100,
                'exact_seven_day_total':170705,'navigation_to_rows_seconds':seconds,'search_to_rows_seconds':refresh_seconds,
                'rows_ready_while_policy_pending':True,'renderer':snapshot(page),
                'served_assets':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (shell.parent/'ui').iterdir() if p.is_file()},
                'production_history_used':False,'production_policy_changed':False,'installed_client_changed':False}
            page.screenshot(path=str(output/'recent-dns.png'))
            (output/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in report.items() if k not in ('renderer','served_assets')}),flush=True)
        finally:release.set();session.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output)
