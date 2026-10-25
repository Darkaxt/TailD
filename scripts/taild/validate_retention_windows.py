"""R39 native startup/retention acceptance with held maintenance; synthetic only."""
import argparse,json,threading
from pathlib import Path
from unittest.mock import patch
import history
from test_connectivity import DaemonFixture
from validate_analytics_windows import NativeSession,populate,capture_preview,settled


def run(shell,output):
    from playwright.sync_api import sync_playwright,expect
    output.mkdir(parents=True,exist_ok=False)
    home=output/'history';populate(home)
    entered,release=threading.Event(),threading.Event()
    original=history.History.cleanup_batch
    def held(store,**kwargs):
        entered.set();release.wait()
        return original(store,**kwargs)
    session=None
    try:
        with sync_playwright() as playwright,patch.object(history.History,'cleanup_batch',held):
            session=NativeSession(shell,home,playwright,open_overview=False)
            entered.wait()
            assert session.collector.ready.is_set() and not release.is_set()
            session.collector.connectivity.call=DaemonFixture()
            page=session.page
            assert page.url=='https://taild.local/index.html'
            page.locator('#connectivity-reload').click()
            expect(page.locator('#connection-devices')).to_contain_text('Test device')
            expect(page.locator('#connectivity-toggle')).to_be_checked()
            capture_preview(session,output/'connection-during-maintenance.png')
            page.locator('#nav-preferences').click()
            page.wait_for_function("()=>document.querySelector('#analytics-toggle')&&!document.querySelector('#analytics-toggle').disabled",timeout=0)
            capture_preview(session,output/'preferences-during-maintenance.png')
            page.locator('#category-analytics').click()
            settled(page)
            assert not release.is_set(),'Read/UI readiness incorrectly waited for cleanup'
            capture_preview(session,output/'overview-during-maintenance.png')
            release.set()
            # This command is queued behind the original maintenance operation;
            # its receipt proves that operation completed without cancellation.
            status=session.collector.command('state')
            assert status['maintenance']['state']=='idle'
            (output/'verified.json').write_text(json.dumps({'native_url':page.url,
                'collector_and_native_ready_before_cleanup':True,'device_controls_before_cleanup':True,
                'preferences_before_cleanup':True,'analytics_reads_before_cleanup':True,
                'maintenance_completed':True,'production_history_used':False},indent=2))
    finally:
        release.set()
        if session is not None:session.close()
    print(json.dumps({'verified':True,'output':str(output)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output.resolve())
