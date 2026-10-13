import contextlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import unittest
from unittest.mock import patch

import controld


class ControlDTest(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.responses = {
            '/users': (200, {'success': True, 'body': {'stats_endpoint': 'synthetic-org', 'org_id': None}}),
            '/devices': (200, {'success': True, 'body': {'devices': [
                {'PK': 'synthetic-device', 'name': 'Synthetic', 'unknown': 'preserved'}]}}),
            '/profiles': (200, {'success': True, 'body': {'profiles': [{'PK': 'synthetic-profile'}]}}),
        }
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append((self.path, self.headers.get('Authorization'),
                                       self.headers.get('X-Force-Org-Id')))
                status, body = owner.responses[self.path]
                self.send_response(status)
                if status == 302:
                    self.send_header('Location', '/profiles')
                if status == 429:
                    self.send_header('Retry-After', '120')
                self.end_headers()
                self.wfile.write((json.dumps(body) if isinstance(body, dict) else body).encode())

            def log_message(self, *args):
                pass

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        self.api_patch = patch.object(controld, 'API_BASE', self.base)
        self.api_patch.start()
        self.addCleanup(self.api_patch.stop)
        self.clock_patch = patch.object(controld, 'utc_now',
                                       return_value=datetime(2026, 10, 7, 8, tzinfo=timezone.utc))
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)

    def stop_server(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_inventory_performs_only_two_authenticated_gets_and_preserves_fields(self):
        result = controld.inventory('synthetic-token')
        self.assertEqual(result['devices'][0]['unknown'], 'preserved')
        self.assertEqual(self.requests, [('/devices', 'Bearer synthetic-token', None),
                                        ('/profiles', 'Bearer synthetic-token', None)])

    def test_redirect_is_rejected_without_a_second_request(self):
        self.responses['/devices'] = (302, 'not followed')
        with self.assertRaises(controld.ControlDError):
            controld.inventory('synthetic-token')
        self.assertEqual(len(self.requests), 1)

    def test_http_error_does_not_echo_token_or_service_response(self):
        self.responses['/devices'] = (403, {'error': 'synthetic-token private-account'})
        with self.assertRaises(controld.ControlDError) as raised:
            controld.inventory('synthetic-token')
        self.assertIn('403', str(raised.exception))
        self.assertNotIn('synthetic-token', str(raised.exception))
        self.assertNotIn('private-account', str(raised.exception))

    def policy_responses(self):
        self.responses['/devices?last_activity=1'] = (200, {'success': True, 'body': {'devices': [
            {'PK': 'device', 'profile': {'PK': 'profile'}, 'clients': [{'PK': 'client'}]}]}})
        self.responses['/profiles'] = (200, {'success': True, 'body': {'profiles': [{'PK': 'profile'}]}})
        self.responses['/profiles/restrictions'] = (200, {'success': True, 'body': {'restrictions': []}})
        for resource, controller in (('filters','filters'), ('filters/external','filters'),
                                     ('services','services'), ('rules/all','rules'),
                                     ('groups','groups'), ('options','options'),
                                     ('restrictions','restrictions'), ('default','default')):
            self.responses['/profiles/profile/'+resource] = (200, {'success': True, 'body': {
                controller: [] if controller != 'default' else {'do': 999, 'status': 1}}})

    def test_selected_endpoint_policy_reads_every_verified_category_without_writes(self):
        self.assertTrue(hasattr(controld, 'policy_snapshot'), 'Stage 6 policy reader missing')
        self.policy_responses()
        self.responses['/profiles/profile/rules/all'][1]['body']['rules'] = [
            {'PK':'example.invalid','do':999,'future_field':{'raw':True}}]
        result = controld.policy_snapshot('synthetic-token', 'device', account_scope='synthetic-account')
        self.assertEqual(result['endpoint'], 'device')
        self.assertEqual(result['profile'], 'profile')
        self.assertEqual(result['resources']['rules']['data']['rules'][0]['future_field'], {'raw':True})
        self.assertEqual(result['resources']['restrictions']['state'], 'available')
        self.assertEqual(result['consistency'], 'separate-api-reads')
        self.assertTrue(all(r[1]=='Bearer synthetic-token' for r in self.requests))
        self.assertNotIn('synthetic-token', json.dumps(result))
        self.assertEqual(len(self.requests), 12)

    def test_capabilities_preserve_denial_rate_limit_pagination_and_later_categories(self):
        self.assertTrue(hasattr(controld, 'policy_snapshot'), 'Stage 6 policy reader missing')
        self.policy_responses()
        self.responses['/profiles/profile/filters'] = (403, 'private synthetic-token')
        self.responses['/profiles/profile/services'] = (429, 'private synthetic-token')
        self.responses['/profiles/profile/rules/all'][1]['body']['next_cursor'] = 'opaque-next'
        result = controld.policy_snapshot('synthetic-token', 'device', account_scope='account')
        self.assertEqual(result['resources']['filters']['state'], 'denied')
        self.assertEqual(result['resources']['services']['state'], 'rate-limited')
        self.assertEqual(result['resources']['services']['retry_after'], 120)
        self.assertEqual(result['resources']['rules']['state'], 'incomplete')
        self.assertEqual(result['resources']['restrictions']['state'], 'available')
        self.assertEqual(len(self.requests), 12)  # No retry or guessed pagination route.
        self.assertNotIn('synthetic-token', json.dumps(result))

    def test_policy_unknown_endpoint_and_path_injection_fail_before_policy_reads(self):
        self.assertTrue(hasattr(controld, 'policy_snapshot'), 'Stage 6 policy reader missing')
        self.policy_responses()
        for endpoint in ('../users', 'device?secret=yes', 'device/other'):
            with self.assertRaises(controld.ControlDError):
                controld.policy_snapshot('synthetic-token', endpoint, account_scope='account')
        self.assertEqual(self.requests, [])
        with self.assertRaises(controld.ControlDError):
            controld.policy_snapshot('synthetic-token', 'missing', account_scope='account')
        self.assertFalse(any('/profiles/profile/' in r[0] for r in self.requests))

    def test_policy_malformed_known_category_and_credential_echo_are_not_available(self):
        self.assertTrue(hasattr(controld, 'policy_snapshot'), 'Stage 6 policy reader missing')
        self.policy_responses()
        self.responses['/profiles/profile/services'] = (200, {'success': True, 'body': {'services':'bad'}})
        self.responses['/profiles/profile/rules/all'] = (200, {'success': True, 'body': {
            'rules':[{'value':'synthetic-token'}]}})
        result=controld.policy_snapshot('synthetic-token','device',account_scope='account')
        self.assertEqual(result['resources']['services']['state'],'incompatible')
        self.assertEqual(result['resources']['rules']['state'],'incompatible')
        self.assertNotIn('synthetic-token',json.dumps(result))

    def test_http_429_keeps_sanitized_retry_metadata(self):
        self.responses['/devices']=(429, 'synthetic-token')
        with self.assertRaises(controld.ControlDError) as raised:
            controld.inventory('synthetic-token')
        self.assertEqual(getattr(raised.exception,'retry_after',None),120)
        self.assertEqual(getattr(raised.exception,'status',None),429)

    def test_missing_inventory_clients_use_verified_scoped_analytics_read(self):
        self.policy_responses()
        del self.responses['/devices?last_activity=1'][1]['body']['devices'][0]['clients']
        original=controld._read
        urls=[]
        def read(url,token,organization=None):
            if '.analytics.controld.com/v2/client?' in url:
                urls.append(url)
                return io.BytesIO(json.dumps({'success':True,'body':{'items':{
                    'device':{'clients':{'synthetic-client':{'host':'synthetic-host','future':1}}},
                    'other-device':{'clients':{'private-peer':{}}}}}}).encode())
            return original(url,token,organization)
        with patch.object(controld,'_read',side_effect=read):
            result=controld.policy_snapshot('synthetic-token','device',account_scope='account')
        self.assertEqual(result['resources']['clients']['state'],'available')
        self.assertEqual(set(result['resources']['clients']['data']['items']),{'device'})
        self.assertEqual(len(urls),1)
        self.assertTrue(urls[0].endswith('/v2/client?endpointId=device'))
        self.assertNotIn('private-peer',json.dumps(result['resources']['clients']))

    def test_policy_cli_hidden_vault_token_to_private_history_and_summary(self):
        import credentials
        import analytics
        import history
        self.policy_responses()
        class Vault:
            def read(self): return 'synthetic-token'
        with tempfile.TemporaryDirectory(prefix='taild-policy-cli-',dir='D:/Temp' if os.name=='nt' else None) as directory:
            output=io.StringIO()
            folder=Path(directory)/'history'
            with patch.object(credentials,'CredentialStore',return_value=Vault()), \
                 contextlib.redirect_stdout(output):
                result=controld.main(['--token-vault','policy','--endpoint','device',
                    '--account-scope','account','--history',str(folder)])
            self.assertEqual(result,0)
            self.assertNotIn('synthetic-token',output.getvalue())
            self.assertNotIn('synthetic-device',output.getvalue())
            store=history.History(folder,now='2026-10-07T08:01:00Z')
            try:
                page=analytics.Analytics(store).batch([{'kind':'policy','view':'facts',
                    'start':'2026-10-07T07:59:00Z','end':'2026-10-07T08:01:00Z',
                    'scope':{'account':'account','endpoint':'device'}}])['results'][0]['data']['rows']
                self.assertEqual(len(page),1)
                self.assertEqual(page[0]['profile'],'profile')
            finally: store.close()

    def test_logical_denial_and_network_failure_have_capability_states(self):
        self.policy_responses()
        self.responses['/profiles/profile/filters']=(200,{'success':False,'error':{'code':403001,'message':'private'}})
        self.responses['/profiles/profile/services']=(200,{'success':False,'error':{'code':429001}})
        result=controld.policy_snapshot('synthetic-token','device',account_scope='account')
        self.assertEqual(result['resources']['filters']['state'],'denied')
        self.assertEqual(result['resources']['services']['state'],'rate-limited')
        from urllib.error import URLError
        with patch.object(controld,'build_opener') as opener:
            opener.return_value.open.side_effect=URLError('synthetic-token')
            with self.assertRaises(controld.ControlDError) as raised:
                controld.inventory('synthetic-token')
        self.assertEqual(raised.exception.state,'stale')
        self.assertNotIn('synthetic-token',str(raised.exception))

    def test_logical_error_even_with_http_200_is_rejected_without_echo(self):
        self.responses['/devices'] = (200, {'success': False, 'body': [],
                                          'error': {'message': 'private-account'}})
        with self.assertRaises(controld.ControlDError) as raised:
            controld.inventory('synthetic-token')
        self.assertNotIn('private-account', str(raised.exception))

    def test_malformed_inventory_is_not_success(self):
        for payload in ({'success': 1, 'body': {'devices': []}},
                        {'success': True, 'body': []},
                        {'success': True, 'body': {'devices': 'not an array'}}):
            self.responses['/devices'] = (200, payload)
            with self.assertRaises(controld.ControlDError):
                controld.inventory('synthetic-token')

    def test_header_injection_is_rejected_before_network_access(self):
        for token in ('', 'synthetic\r\nInjected: yes'):
            with self.assertRaises(controld.ControlDError):
                controld.inventory(token)
        self.assertEqual(self.requests, [])

    def test_observed_personal_csv_interface_is_not_artificially_restricted(self):
        csv = 'timestamp,endpointId,question,action\n2026-10-07T07:00:00Z,synthetic-device,example.invalid,1\n'
        with patch.object(controld, '_read', return_value=io.BytesIO(csv.encode())):
            result = controld.activity('synthetic-token', 'personal', 'synthetic-org',
                                       '2026-10-07T07:00:00Z')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['source'], 'controld-activity-csv')

    def test_analytics_region_comes_from_authenticated_account_metadata(self):
        self.assertEqual(controld.analytics_instance('synthetic-token'), 'synthetic-org')
        self.assertEqual(self.requests, [('/users', 'Bearer synthetic-token', None)])

    def test_account_metadata_cannot_send_credentials_to_an_arbitrary_host(self):
        self.responses['/users'] = (200, {'success': True, 'body': {'stats_endpoint': 'https://example.invalid'}})
        with self.assertRaises(controld.ControlDError):
            controld.analytics_instance('synthetic-token')
        self.assertEqual(len(self.requests), 1)

    def test_organization_metadata_uses_organization_region(self):
        self.responses['/users'] = (200, {'success': True, 'body': {
            'stats_endpoint': 'personal-region', 'org': {'stats_endpoint': 'organization-region'}}})
        self.assertEqual(controld.analytics_instance('synthetic-token'), 'organization-region')

    def test_analytics_host_and_utc_query_window_are_validated(self):
        for instance in ('example.invalid/path', 'user@host', 'org:443', '', '-org'):
            with self.assertRaises(controld.ControlDError):
                controld.activity('synthetic-token', 'organization', instance,
                                  '2026-10-07T07:00:00Z')
        for timestamp in ('not-time', '2026-10-07T07:00:00', '2026-10-07T07:00:00+02:00'):
            with self.assertRaises(controld.ControlDError):
                controld.activity('synthetic-token', 'organization', 'synthetic-org', timestamp)
        self.assertEqual(self.requests, [])

    def test_activity_stream_preserves_raw_codes_and_bounds_first_slice(self):
        csv = ('timestamp,endpointId,profileId,question,action,trigger,answers\n'
               '2026-10-07T07:00:00Z,synthetic-device,synthetic-profile,example.invalid,1,default,192.0.2.1\n'
               '2026-10-07T07:00:01Z,synthetic-device,,other.invalid,999,unknown,\n')
        with patch.object(controld, '_read', return_value=io.BytesIO(csv.encode())) as read:
            result = controld.activity('synthetic-token', 'organization', 'synthetic-org',
                                       '2026-10-07T07:00:00Z', limit=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['raw']['action'], '1')
        self.assertEqual(result[0]['source'], 'controld-activity-csv')
        url = read.call_args.args[0]
        self.assertTrue(url.startswith('https://synthetic-org.analytics.controld.com/v2/activity-log/csv?'))
        self.assertNotIn('synthetic-token', url)

    def test_csv_missing_decision_columns_is_not_accepted(self):
        with patch.object(controld, '_read', return_value=io.BytesIO(b'timestamp,question\n')):
            with self.assertRaises(controld.ControlDError):
                controld.activity('synthetic-token', 'organization', 'synthetic-org',
                                  '2026-10-07T07:00:00Z')

    def test_activity_slice_preserves_bounds_and_detects_truncation(self):
        csv = ('timestamp,endpointId,question,action,answers\n'
               '2026-10-07T07:00:00Z,synthetic-device,example.invalid,1,192.0.2.1\n'
               '2026-10-07T07:00:01Z,synthetic-device,other.invalid,999,192.0.2.2\n')
        self.assertTrue(hasattr(controld,'activity_slice'), 'Decision slice metadata is missing')
        with patch.object(controld,'_read',return_value=io.BytesIO(csv.encode())):
            result=controld.activity_slice('synthetic-token','personal','synthetic-org',
                '2026-10-07T07:00:00Z','2026-10-07T07:01:00Z',endpoint='synthetic-device',limit=1)
        self.assertTrue(result['truncated'])
        self.assertEqual(len(result['rows']),1)
        self.assertEqual(result['query_window']['start_inclusive'],'2026-10-07T07:00:00Z')
        self.assertEqual(result['endpoint_id'],'synthetic-device')

    def test_cli_stdin_token_and_default_summary_do_not_print_private_records(self):
        stdout = io.StringIO()
        with patch('sys.stdin', io.StringIO('synthetic-token\n')), contextlib.redirect_stdout(stdout):
            code = controld.main(['--token-stdin', 'inventory'])
        self.assertEqual(code, 0)
        summary = json.loads(stdout.getvalue())
        self.assertEqual(summary['device_count'], 1)
        self.assertNotIn('synthetic-token', stdout.getvalue())
        self.assertNotIn('synthetic-device', stdout.getvalue())

    def test_private_export_does_not_overwrite_and_repo_output_is_refused(self):
        temp_root = 'D:/Temp' if os.name == 'nt' else None
        with tempfile.TemporaryDirectory(prefix='taild-export-test-', dir=temp_root) as directory:
            output = Path(directory) / 'private.json'
            controld.export_private(output, {'synthetic': True})
            with self.assertRaises(controld.ControlDError):
                controld.export_private(output, {'replaced': True})
            self.assertEqual(json.loads(output.read_text()), {'synthetic': True})
        with self.assertRaises(controld.ControlDError):
            controld.export_private(Path(controld.__file__).parent / 'private.json', {})


if __name__ == '__main__':
    unittest.main()
