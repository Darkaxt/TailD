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
