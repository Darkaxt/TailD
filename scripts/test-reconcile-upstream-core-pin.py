"""Focused ownership regression checks for upstream module conflicts."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('reconcile', Path(__file__).with_name('reconcile-upstream-core-pin.py'))
reconcile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconcile)


class CorePinConflictTest(unittest.TestCase):
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
        anchor = '\t// GetSyspolicyStringValue returns the current string value for the given system policy.\n'
        upstream = 'type AppContext interface {\n' + anchor + '}\n'
        actual = reconcile.resolve_interface(dict(reconcile.INTERFACE_BLOBS), upstream)
        self.assertIn('ReadPrivateDNSProviderJSON() (string, error)', actual)
        self.assertIn('SetPrivateDNSObservation(enabled bool) error', actual)
        self.assertNotIn('GetPlatformDNSConfig', actual)
        self.assertEqual(actual.count(anchor), 1)
        self.assertTrue(actual.endswith(anchor + '}\n'))

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
