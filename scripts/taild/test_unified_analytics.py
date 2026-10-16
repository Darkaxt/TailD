"""Unified recording consent, compatible settings and live peer contracts."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runtime
import connectivity
from test_connectivity import DaemonFixture


class UnifiedAnalyticsTest(unittest.TestCase):
    def test_one_recording_decision_selects_bound_sources_without_new_disk_schema(self):
        with tempfile.TemporaryDirectory() as root:
            collector=runtime.Collector(Path(root),None)
            collector.due={}
            enabled=collector._execute(None,'analytics-configure',{'enabled':True})
            self.assertTrue(enabled['analytics_enabled'])
            self.assertTrue(collector.config['traffic'])
            self.assertTrue(collector.config['activity'])
            self.assertFalse(collector.config['dns'])
            collector._execute(None,'configure',{'provider':{'account_scope':'fixture',
                'endpoint':'fixture','account_type':'personal','instance':'europe'}})
            self.assertTrue(collector.config['dns'])
            saved=json.loads((Path(root)/'runtime.json').read_text())
            self.assertEqual(set(saved),set(runtime.DEFAULTS))
            disabled=collector._execute(None,'analytics-configure',{'enabled':False})
            self.assertFalse(disabled['analytics_enabled'])
            self.assertFalse(any(collector.config[k] for k in ('traffic','dns','activity')))
            self.assertIsNotNone(collector.config['provider'])

    def test_legacy_opt_in_migrates_but_opt_out_remains_off(self):
        self.assertFalse(any(runtime.unified_settings({})[k] for k in ('traffic','dns','activity')))
        legacy=runtime.unified_settings({'activity':True})
        self.assertTrue(legacy['traffic']);self.assertTrue(legacy['activity']);self.assertFalse(legacy['dns'])

    def test_binding_alone_is_not_a_credential(self):
        collector=runtime.Collector(Path('unused'),None)
        collector.config=runtime.settings({'provider':{'account_scope':'fixture',
            'endpoint':'fixture','account_type':'personal','instance':'europe'}})
        with patch.object(runtime.credentials.CredentialStore,'read',return_value=None):
            self.assertFalse(collector._state()['integration_ready']['dns'])

    def test_invalid_global_consent_never_writes_settings(self):
        collector=runtime.Collector(Path('unused'),None)
        for body in ({'enabled':1},{'enabled':True,'token':'not-allowed'},{}):
            with self.assertRaises(runtime.RuntimeError):collector._execute(None,'analytics-configure',body)
        self.assertFalse(collector.config['traffic'])


class LiveInventoryTest(unittest.TestCase):
    def test_metadata_is_live_and_whitelisted_without_tracking_or_cloud_credentials(self):
        daemon=DaemonFixture()
        peer=daemon.status['Peer']['x']
        peer.update(Online=False,LastSeen='2026-10-15T12:00:00Z',OS='linux',UserID=1,
            TaildropTarget=5,NoFileSharingReason='peer is offline',PrimaryRoutes=['10.9.0.0/16'],
            Tags=['tag:server'],Created='2025-01-01T00:00:00Z',KeyExpiry='2027-01-01T00:00:00Z',
            CapMap={'https://tailscale.com/cap/ssh':[]},sshHostKeys=['do-not-expose-host-keys'])
        control=connectivity.Connectivity(None,call=daemon)
        row=control.read()['peers'][0]
        self.assertEqual(row['last_seen'],'2026-10-15T12:00:00Z')
        self.assertEqual(row['owner'],'test@example.invalid')
        self.assertEqual(row['taildrop'],'Offline')
        self.assertEqual(row['routes'],['10.9.0.0/16'])
        self.assertEqual(row['ssh'],'Advertised')
        self.assertNotIn('sshHostKeys',json.dumps(row))
        self.assertNotIn('PublicKey',json.dumps(row))
        self.assertEqual(daemon.writes,[])

    def test_subnet_metadata_excludes_device_addresses_and_default_exit_routes(self):
        daemon=DaemonFixture();daemon.status['Peer']['x']['AllowedIPs']=[
            '100.64.0.2/32','0.0.0.0/0','::/0','192.168.20.0/24','invalid']
        row=connectivity.Connectivity(None,call=daemon).read()['peers'][0]
        self.assertEqual(row['routes'],['192.168.20.0/24'])

    def test_missing_metadata_remains_unknown_and_zero_time_is_not_last_contact(self):
        daemon=DaemonFixture();daemon.status['Peer']['x'].update(Online=None,LastSeen='0001-01-01T00:00:00Z')
        row=connectivity.Connectivity(None,call=daemon).read()['peers'][0]
        self.assertIsNone(row['online']);self.assertIsNone(row['last_seen'])
        self.assertEqual(row['taildrop'],'Not reported');self.assertEqual(row['ssh'],'Not reported')


if __name__=='__main__':unittest.main()
