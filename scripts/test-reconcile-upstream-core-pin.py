"""Focused ownership regression checks for upstream module conflicts."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('reconcile', Path(__file__).with_name('reconcile-upstream-core-pin.py'))
reconcile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconcile)


class CorePinConflictTest(unittest.TestCase):
    def test_shortcuts_keep_classes_and_policy_but_target_fork_identity(self):
        texts = {
            reconcile.SHORTCUT: 'android:targetPackage="com.tailscale.ipn"\n' * 2 +
                'android:action="com.tailscale.ipn.CONNECT_VPN"\n' +
                'android:action="com.tailscale.ipn.DISCONNECT_VPN"\n' +
                'android:targetClass="com.tailscale.ipn.AutomationActivity"\n',
            reconcile.MANIFEST: 'android:excludeFromRecents="true"\n' +
                'android:name="com.tailscale.ipn.CONNECT_VPN"\n' +
                'android:name="com.tailscale.ipn.DISCONNECT_VPN"\n',
            reconcile.STRINGS: '<string name="shortcut_connect_long">Connect to Tailscale</string>\n' +
                '<string name="shortcut_disconnect_long">Disconnect from Tailscale</string>\n' +
                '<string name="attribution">Tailscale</string>\n',
        }
        result = reconcile.resolve_shortcuts(reconcile.SHORTCUT_BLOBS, texts)
        self.assertIn('android:targetPackage="io.github.darkaxt.taildns"', result[reconcile.SHORTCUT])
        self.assertIn('android:targetClass="com.tailscale.ipn.AutomationActivity"', result[reconcile.SHORTCUT])
        self.assertIn('android:name="${applicationId}.CONNECT_VPN"', result[reconcile.MANIFEST])
        self.assertIn('android:excludeFromRecents="true"', result[reconcile.MANIFEST])
        self.assertIn('Connect to TailDNS', result[reconcile.STRINGS])
        self.assertIn('<string name="attribution">Tailscale</string>', result[reconcile.STRINGS])
        for path in reconcile.SHORTCUT_BLOBS:
            blobs = dict(reconcile.SHORTCUT_BLOBS)
            blobs[path] = '0' * 40
            with self.subTest(path=path), self.assertRaises(ValueError):
                reconcile.resolve_shortcuts(blobs, texts)
        texts[reconcile.SHORTCUT] += 'android:targetPackage="com.tailscale.ipn"\n'
        with self.assertRaises(ValueError):
            reconcile.resolve_shortcuts(reconcile.SHORTCUT_BLOBS, texts)

    def test_reviewed_dns_migration_preserves_both_implementations(self):
        reconcile.validate_paths({'go.mod', 'go.sum', *reconcile.DNS_BLOBS})
        result = reconcile.resolve_dns(reconcile.DNS_UPSTREAM, reconcile.DNS_BLOBS,
                                       reconcile.DNS_SOURCE_BLOB)
        self.assertEqual(set(result), set(reconcile.DNS_PAYLOADS))
        view = result[reconcile.DNS_VIEW]
        self.assertIn('collectAsStateWithLifecycle()', view)
        self.assertIn('Modifier.padding(innerPadding)', view)
        self.assertIn('onSaveLocalDNS(', view)
        self.assertIn('isLocalDNSToggleEnabled(', view)
        self.assertIn('remember(saved.ProfileID, saved.ManualEndpoint)', view)
        self.assertIn('local_dns_tailnet_resolvers', view)

    def test_dns_resolution_rejects_every_unknown_input(self):
        for path in reconcile.DNS_BLOBS:
            for stage in ('1', '2', '3'):
                blobs = {p: dict(v) for p, v in reconcile.DNS_BLOBS.items()}
                blobs[path][stage] = '0' * 40
                with self.subTest(path=path, stage=stage), self.assertRaises(ValueError):
                    reconcile.resolve_dns(reconcile.DNS_UPSTREAM, blobs,
                                          reconcile.DNS_SOURCE_BLOB)
        for upstream, companion in (('0' * 40, reconcile.DNS_SOURCE_BLOB),
                                    (reconcile.DNS_UPSTREAM, '0' * 40)):
            with self.assertRaises(ValueError):
                reconcile.resolve_dns(upstream, reconcile.DNS_BLOBS, companion)

    def test_changed_dns_payload_is_rejected_before_resolution(self):
        with mock.patch.object(Path, 'read_bytes', return_value=b'changed reviewed source'):
            with self.assertRaisesRegex(ValueError, 'payload changed'):
                reconcile.resolve_dns(reconcile.DNS_UPSTREAM, reconcile.DNS_BLOBS,
                                      reconcile.DNS_SOURCE_BLOB)

    def test_only_core_requirement_uses_fork_pin_and_preserves_merged_dependency(self):
        text = ('require (\n\tother.example/module v2.0.0\n<<<<<<< HEAD\n'
                '\ttailscale.com v1.2.3-fork\n=======\n'
                '\ttailscale.com v1.2.4-upstream\n>>>>>>> upstream\n)\n')
        result = reconcile.resolve(text, 'go.mod')
        self.assertIn('other.example/module v2.0.0', result)
        self.assertIn('tailscale.com v1.2.3-fork', result)
        self.assertNotIn('v1.2.4-upstream', result)

    def test_only_vanilla_core_sums_conflict_is_removed_without_losing_fork_sum(self):
        text = ('github.com/Darkaxt/tailscale v1.2.3 h1:fork=\n<<<<<<< HEAD\n'
                '=======\ntailscale.com v1.2.4 h1:upstream=\n>>>>>>> upstream\n')
        self.assertEqual(reconcile.resolve(text, 'go.sum'),
                         'github.com/Darkaxt/tailscale v1.2.3 h1:fork=\n')

    def test_unrelated_module_conflict_is_rejected(self):
        for path, text in (
            ('go.mod', '<<<<<<< HEAD\n other.example/a v1\n=======\n other.example/a v2\n>>>>>>> upstream\n'),
            ('go.sum', '<<<<<<< HEAD\nother.example/a v1 h1:abc=\n=======\n>>>>>>> upstream\n')):
            with self.subTest(path=path), self.assertRaises(ValueError):
                reconcile.resolve(text, path)

    def test_missing_or_nested_markers_are_rejected(self):
        for text in ('<<<<<<< HEAD\n', '<<<<<<< HEAD\n<<<<<<< nested\n=======\n>>>>>>> x\n'):
            with self.assertRaises(ValueError):
                reconcile.resolve(text, 'go.mod')

    def test_complete_conflict_set_is_required(self):
        with self.assertRaises(ValueError):
            reconcile.validate_paths({'go.mod', 'go.sum', 'android/source.kt'})

    def test_reviewed_interface_preserves_observer_and_upstream_network_callback(self):
        reconcile.validate_paths({'go.mod', 'go.sum', reconcile.INTERFACE_PATH})
        legacy = ('\t// GetPlatformDNSConfig gets a string representation of the current DNS\n'
                  '\t// configuration.\n\tGetPlatformDNSConfig() string\n\n')
        observer = ('\t// ReadPrivateDNSProviderJSON reads the saved hostname and system mode without\n'
                    '\t// privileged APIs. SetPrivateDNSObservation registers before the first read.\n'
                    '\tReadPrivateDNSProviderJSON() (string, error)\n'
                    '\tSetPrivateDNSObservation(enabled bool) error\n\n')
        prefix = 'type AppContext interface {\n'
        suffix = '}\ntype Application interface {\n\tNotifyPrivateDNSChanged()\n}\n'
        merged = prefix + '<<<<<<< HEAD\n' + legacy + observer + '=======\n>>>>>>> ' + '1' * 40 + '\n' + suffix
        actual = reconcile.resolve_interface(dict(reconcile.INTERFACE_BLOBS), merged)
        self.assertIn('ReadPrivateDNSProviderJSON() (string, error)', actual)
        self.assertIn('SetPrivateDNSObservation(enabled bool) error', actual)
        self.assertNotIn('GetPlatformDNSConfig', actual)
        self.assertEqual(actual, prefix + observer + suffix)
        self.assertIn('NotifyPrivateDNSChanged()', actual)
        with self.assertRaises(ValueError):
            reconcile.resolve_interface(dict(reconcile.INTERFACE_BLOBS), merged.replace('GetPlatformDNSConfig() string', 'Changed() string'))

    def test_each_unreviewed_interface_blob_is_rejected(self):
        for stage in ('1', '2', '3'):
            blobs = dict(reconcile.INTERFACE_BLOBS)
            blobs[stage] = '0' * 40
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                reconcile.resolve_interface(blobs, '')

    def test_fork_workflow_policy_is_restored_before_source_resolution(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/upstream-candidate.yml').read_text()
        restore = 'git restore --source="origin/$base" --staged --worktree -- .github/workflows'
        self.assertLess(workflow.index(restore), workflow.index('python3 -B scripts/reconcile-upstream-core-pin.py --upstream'))


if __name__ == '__main__':
    unittest.main()
