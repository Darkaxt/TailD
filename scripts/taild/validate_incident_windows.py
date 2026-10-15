"""Actual native WebView/pipe/manager controls with isolated provider fixtures."""
import argparse
import copy
from datetime import datetime,timezone
import json
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright,expect
import history
import management
from test_management import snapshot as policy_fixture
from validate_analytics_windows import NativeSession,populate,settled


def run(shell, output):
    output.mkdir(parents=True,exist_ok=False)
    populate(output/'history')
    fixture=policy_fixture();fixture['resources']['endpoints']['data']['devices'].append(
        {'PK':'second','name':'Shared test device','profile':{'PK':'profile'}})
    fixture['resources']['filters']['data']['filters'][0]['name']='Ads & Trackers'
    fixture['resources']['options']['data']['options'][0].update(type='toggle',title='Block private addresses',configured=True)
    writes=[]
    def write(token,method,route,payload,org=None):
        writes.append((method,route))
        if route.endswith('/rules'):
            fixture['resources']['rules']['data']['rules']=[{'PK':payload['hostnames[]'][0],
                'group':payload.get('group',0),'comment':payload.get('comment',''),
                'action':{'do':payload['do'],'status':payload['status']}}]
        elif '/filters/' in route:
            fixture['resources']['filters']['data']['filters'][0].update(status=payload['status'],action={'lvl':route.rsplit('/',1)[1]})
        elif '/services/' in route:
            fixture['resources']['services']['data']['services'][0]['action']=payload.copy()
        elif '/options/' in route:
            fixture['resources']['options']['data']['options'][0]['value']=int(payload['status'])
        return {}
    with sync_playwright() as playwright,patch.object(management,'write',side_effect=write):
        session=NativeSession(shell,output/'history',playwright)
        try:
            page=session.page;page.set_default_timeout(0);settled(page)
            page.locator('#time-range').select_option('custom');settled(page)
            # The exact native-served map card must not inherit the two-row stretch.
            card=page.locator('#dashboard-map')
            geometry=card.evaluate('e=>({align:getComputedStyle(e).alignSelf,height:e.getBoundingClientRect().height,scroll:e.scrollHeight})')
            assert geometry['align']=='start',geometry
            page.screenshot(path=str(output/'dashboard.png'))
            session.collector.command('configure',{'provider':{'account_scope':'local','endpoint':'device','account_type':'personal','instance':'acceptance'}})
            manager=session.collector.management
            def read(endpoint,*args):
                value=copy.deepcopy(fixture);value['endpoint']=endpoint;return value
            manager._read=read
            manager._write_token=lambda *args:'synthetic-test-write'
            def recent_fact():
                now=datetime.now(timezone.utc).isoformat()
                session.collector.store.import_live_dns({'timestamp':now,'endpointId':'device',
                    'question':'blocked-example.invalid','profileId':'profile','rrType':'A','action':'0',
                    'trigger':'filter','triggerValue':'ads','categories':[{'categoryName':'Technology'}]},
                    'local','device',collected=now)
            session.collector._commit(recent_fact)
            page.locator('#nav-3').click();settled(page)
            page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'")
            expect(page.locator('.incident-binding h2')).to_have_text('Shared')
            page.locator('.incident-scope-details>summary').click()
            expect(page.locator('#management-binding .incident-endpoints .filter-pill')).to_have_count(2)
            page.locator('.incident-scope-details>summary').click()
            expect(page.locator('#management-recent')).to_contain_text('Filter / list · Ads & Trackers (ads)')
            incident_geometry=page.evaluate('''()=>({recent:document.querySelector('#management-recent').getBoundingClientRect().top,
              policy:document.querySelector('#management-policy').getBoundingClientRect().top,
              tabs:document.querySelector('.incident-tabs').getBoundingClientRect().top})''')
            assert incident_geometry['recent']<incident_geometry['tabs']<incident_geometry['policy'],incident_geometry
            page.screenshot(path=str(output/'incident-first.png'))
            page.locator('#management-recent').get_by_text('Decision details',exact=True).click()
            expect(page.locator('#management-recent')).to_contain_text('Classification: Technology')
            # Recent-resolution actions use the existing guarded write workflow.
            page.locator('#management-recent').get_by_role('button',name='Allow',exact=True).click()
            expect(page.locator('#management-preview')).to_contain_text('Allow · explicit Bypass')
            expect(page.locator('#management-apply')).to_be_disabled()
            assert not writes
            page.locator('#management-confirm').check();page.locator('#management-apply').click()
            page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'")
            assert len(writes)==1
            expect(page.locator('#management-policy')).to_contain_text('blocked-example.invalid')
            page.locator('#incident-hostname').fill('example.invalid')
            page.locator('#incident-preview-rule').click()
            expect(page.locator('#management-preview')).to_be_visible()
            expect(page.locator('#management-apply')).to_be_disabled()
            assert len(writes)==1
            page.locator('#management-confirm').check();page.locator('#management-apply').click()
            page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'")
            assert len(writes)==2
            expect(page.locator('.incident-workspace .error')).to_have_count(0)
            expect(page.locator('#management-policy')).to_contain_text('example.invalid')
            # A shared-scope change between preview and Apply cannot mutate.
            page.locator('#incident-hostname').fill('conflict.invalid');page.locator('#incident-preview-rule').click()
            expect(page.locator('#management-preview')).to_be_visible()
            fixture['resources']['endpoints']['data']['devices'].pop()
            page.locator('#management-confirm').check();page.locator('#management-apply').click()
            expect(page.locator('.incident-workspace .error')).to_contain_text('changed')
            assert len(writes)==2
            fixture['resources']['endpoints']['data']['devices'].append(
                {'PK':'second','name':'Shared test device','profile':{'PK':'profile'}})
            page.locator('#management-reload').click()
            page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'")
            for tab,button in (('Filters','Enable selected'),('Services','Allow · Bypass'),('Profile Options','Enable / set')):
                page.get_by_role('button',name=tab,exact=True).click()
                page.get_by_role('button',name=button,exact=True).first.click()
                expect(page.locator('#management-preview')).to_be_visible()
                page.locator('#management-confirm').check();page.locator('#management-apply').click()
                page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'")
                expect(page.locator('.incident-workspace .error')).to_have_count(0)
            page.screenshot(path=str(output/'management.png'))
            # Existing redirect/spoof actions cannot be silently coerced by a toggle.
            fixture['resources']['rules']['data']['rules'].append({'PK':'spoof.invalid','action':{'do':2,'status':1}})
            page.locator('#management-reload').click()
            page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'")
            page.get_by_role('button',name='Rules',exact=True).click()
            row=page.locator('#management-policy tr').filter(has_text='spoof.invalid')
            expect(row.get_by_role('button',name='Disable',exact=True)).to_be_disabled()
            row.get_by_role('button',name='Replace action…',exact=True).click()
            expect(page.locator('#incident-preview-rule')).to_be_disabled()
            # A failed endpoint read clears the old binding and action surface.
            def rejected(endpoint,*args):
                if endpoint=='second':raise management.ManagementError('management-resource-unavailable')
                return read(endpoint,*args)
            manager._read=rejected
            page.locator('#management-endpoint').select_option('second')
            expect(page.locator('.incident-workspace .error')).to_be_visible()
            expect(page.locator('.incident-binding h2')).to_have_text('Not loaded')
            expect(page.locator('#incident-preview-rule')).to_have_count(0)
            manager._read=read
            page.locator('#management-endpoint').select_option('device')
            page.wait_for_function("()=>document.querySelector('.incident-workspace')?.getAttribute('aria-busy')==='false'")
            # One pending recent read coalesces explicit search changes, even
            # with Follow off. Stale results cannot appear under the new text.
            page.locator('.incident-recent-controls input[type=checkbox]').uncheck()
            entered=threading.Event();release=threading.Event();original=session.collector.dispatch;searches=[]
            def held_query(request,**kwargs):
                queries=request.get('body',{}).get('queries',[])
                if request.get('op')=='view-query' and queries:searches.append(queries[0].get('search'))
                if request.get('op')=='view-query' and queries and queries[0].get('search')=='alpha':
                    entered.set();release.wait()
                return original(request,**kwargs)
            session.collector.dispatch=held_query
            try:
                page.locator('#incident-dns-search').fill('alpha');entered.wait()
                page.locator('#incident-dns-search').fill('beta')
                release.set()
                page.wait_for_function("()=>document.querySelector('#incident-dns-refresh')?.textContent?.trim()==='Refresh DNS'")
                assert page.locator('#management-recent tbody tr').count()==0
                assert 'beta' in searches,searches
            finally:release.set();session.collector.dispatch=original
            # Active text/background contrast from the actual served assets.
            colors=page.locator('.incident-tabs button.active').evaluate('e=>({fg:getComputedStyle(e).color,bg:getComputedStyle(e).backgroundColor})')
            def luminance(value):
                channels=[int(c)/255 for c in value.removeprefix('rgb(').removesuffix(')').split(',')]
                linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in channels]
                return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))
            levels=sorted((luminance(colors['fg']),luminance(colors['bg'])))
            contrast=(levels[1]+.05)/(levels[0]+.05);assert contrast>=4.5,colors
            page.set_viewport_size({'width':850,'height':800})
            page.get_by_role('button',name='Rules',exact=True).click()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(output/'management-narrow.png'))
            page.set_viewport_size({'width':560,'height':800})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(output/'management-560.png'))
            receipt={'ok':True,'url':page.url,'actual_native_pipe_manager':True,
                'recent_before_policy':True,'recent_incident_guarded_apply':True,
                'incident_layout':incident_geometry,
                'provider_fixture_only':True,'production_mutations':False,'confirmed_writes':len(writes),
                'shared_profile_conflict_rejected':True,'map_geometry':geometry,'narrow_width':850,
                'failed_endpoint_clears_actions':True,'unsupported_rule_toggle_refused':True,
                'coalesced_search_with_follow_off':True,'active_tab_contrast':contrast,
                'blocking_filter_and_category_details':True,'minimum_test_viewport':560}
            (output/'incident-validation.json').write_text(json.dumps(receipt,indent=2))
            print(json.dumps(receipt))
        finally:session.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.shell.resolve(strict=True),args.output)
