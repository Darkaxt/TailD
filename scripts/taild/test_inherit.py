import os
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import inherit


class DependencyReconciliationTest(unittest.TestCase):
    def conflict(self):
        return (b'<<<<<<< HEAD\n'
                b'  implementation("com.squareup.okhttp3:okhttp:4.12.0")\n'
                b'=======\n'
                b'  implementation(libs.coil.network.okhttp)\n'
                b'>>>>>>> 65f924c48a8181d8bb753b1ef9790349b3b30130\n')

    def test_coil_and_fork_okhttp_survive_without_changing_merged_surroundings(self):
        text = b'canonical and fork prefix\n' + self.conflict() + b'merged suffix\n'
        expected = (b'canonical and fork prefix\n'
                    b'  implementation(libs.coil.network.okhttp)\n'
                    b'  implementation("com.squareup.okhttp3:okhttp:4.12.0")\n'
                    b'merged suffix\n')
        self.assertEqual(inherit.reconcile_dependency_hunk(text), expected)

    def test_changed_dependency_or_upstream_hunk_is_rejected(self):
        for before, after in ((b'4.12.0', b'4.13.0'),
                              (b'65f924c48a8181d8bb753b1ef9790349b3b30130', b'unknown')):
            with self.assertRaisesRegex(inherit.InheritanceError, 'dependency conflict'):
                inherit.reconcile_dependency_hunk(self.conflict().replace(before, after))

    def test_duplicate_or_additional_conflict_is_rejected(self):
        for text in (self.conflict() * 2,
                     self.conflict() + b'<<<<<<< HEAD\nother\n=======\nchange\n>>>>>>> other\n'):
            with self.assertRaisesRegex(inherit.InheritanceError, 'dependency conflict'):
                inherit.reconcile_dependency_hunk(text)

    def test_changed_complete_output_is_rejected_before_write_or_commit(self):
        path = 'android/build.gradle.kts'
        blobs = inherit.REVIEWED_RECONCILIATIONS[inherit.DEPENDENCIES_UPSTREAM][path]
        stages = ''.join(f'100644 {blob} {stage}\t{path}\0'
                         for stage, blob in enumerate(blobs, 1))
        with patch.object(inherit, 'git') as git, \
                patch.object(Path, 'read_bytes', return_value=self.conflict() + b'drift'), \
                patch.object(Path, 'write_bytes') as write:
            git.return_value.stdout = stages
            with self.assertRaisesRegex(inherit.InheritanceError, 'dependency output changed'):
                inherit.reconcile_reviewed_merge(Path.cwd(), 'base', inherit.DEPENDENCIES_UPSTREAM)
        write.assert_not_called()
        self.assertEqual(git.call_count, 1, 'Only the conflict-stage read may execute')

    def test_changed_companion_index_prevents_all_output_writes(self):
        path = 'android/build.gradle.kts'
        blobs = inherit.REVIEWED_RECONCILIATIONS[inherit.DEPENDENCIES_UPSTREAM][path]
        stages = ''.join(f'100644 {blob} {stage}\t{path}\0'
                         for stage, blob in enumerate(blobs, 1))
        reads = [subprocess.CompletedProcess([], 0, stdout=stages),
                 subprocess.CompletedProcess([], 0, stdout='unknown companion')]
        with patch.object(inherit, 'git', side_effect=reads) as git, \
                patch.object(inherit, 'reconcile_dependency_hunk', return_value=b'gradle'), \
                patch.object(inherit, 'DEPENDENCIES_SHA256', hashlib.sha256(b'gradle').hexdigest()), \
                patch.object(Path, 'read_bytes', return_value=b'gradle'), \
                patch.object(Path, 'write_bytes') as write:
            with self.assertRaisesRegex(inherit.InheritanceError, 'companion index changed'):
                inherit.reconcile_reviewed_merge(Path.cwd(), 'base', inherit.DEPENDENCIES_UPSTREAM)
        write.assert_not_called()
        self.assertEqual(git.call_count, 2, 'Only source/index reads may execute')

    def test_prepared_chart_payload_is_pinned_and_keeps_hourly_contract(self):
        root = Path(inherit.__file__).parent / 'inheritance-resolutions/20261114'
        data = (root / 'FirewallDiagnosis.kt').read_bytes().replace(b'\r\n', b'\n')
        self.assertEqual(hashlib.sha256(data).hexdigest(), inherit.DEPENDENCIES_COMPANION_SHA256)
        text = data.decode()
        for marker in ('series(y = received.map { it.second })',
                       'series(y = sent.map { it.second })', 'MergeMode.Stacked',
                       'height(if (compact) 88.dp else 132.dp)',
                       'zoomEnabled = false, initialZoom = Zoom.Content',
                       'scrollEnabled = false', 'contentDescription = description',
                       'Hourly traffic unavailable', 'No recorded traffic'):
            self.assertIn(marker, text)
        self.assertNotIn('com.patrykandpatrick.vico.core.', text)


class SettingsReconciliationTest(unittest.TestCase):
    def test_reviewed_payloads_are_pinned(self):
        root = Path(inherit.__file__).parent / 'inheritance-resolutions' / '20261113'
        for _, (name, digest) in inherit.SETTINGS_PAYLOADS.items():
            data = (root / name).read_bytes().replace(b'\r\n', b'\n')
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest)

    def test_changed_payload_is_rejected_before_any_git_or_write(self):
        with patch.object(Path, 'read_bytes', return_value=b'unreviewed'), \
                patch.object(inherit, 'git') as git:
            with self.assertRaisesRegex(inherit.InheritanceError, 'payload changed'):
                inherit.settings_outputs(Path.cwd())
        git.assert_not_called()

    def test_changed_companion_index_prevents_all_output_writes(self):
        with patch.object(inherit, 'git') as git, \
                patch.object(Path, 'write_bytes') as write:
            git.return_value.stdout = '100644 unknown 0\tunexpected'
            with self.assertRaisesRegex(inherit.InheritanceError, 'companion index changed'):
                inherit.settings_outputs(Path.cwd())
        write.assert_not_called()

    def test_shortcuts_keep_package_and_actions_while_rebranding_labels(self):
        text = ('Connect to TailDNS\nDisconnect from TailDNS\nTailDNS launcher package\n'
                'io.github.darkaxt.taildns.CONNECT\ncom.tailscale.ipn.AutomationActivity\n')
        actual = inherit.settings_companion('scripts/test-shortcut-identity.py', text)
        self.assertEqual(actual, text.replace('to TailDNS', 'to TailD')
                         .replace('from TailDNS', 'from TailD')
                         .replace('TailDNS launcher', 'TailD launcher'))

    def test_changed_or_duplicate_label_is_rejected(self):
        for text in ('unknown', 'Connect to TailDNS\nConnect to TailDNS'):
            with self.assertRaisesRegex(inherit.InheritanceError, 'companion changed'):
                inherit.settings_companion('android/src/main/res/values/strings.xml', text)


class InheritanceTest(unittest.TestCase):
    def setUp(self):
        temp_root = 'D:/Temp' if os.name == 'nt' else None
        self.temp = tempfile.TemporaryDirectory(prefix='taild-git-test-', dir=temp_root)
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Synthetic Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.write('go.mod', 'module example.invalid/test\n\nrequire tailscale.com v1.2.3\n'
                   'replace tailscale.com => github.com/Darkaxt/tailscale v1.2.3\n')
        self.write('android/dns.txt', 'original DNS\n')
        self.commit('original')
        self.git('branch', 'upstream')
        self.write('scripts/taild/feature.txt', 'local analytics\n')
        self.commit('local extension')
        self.base = self.git('rev-parse', 'HEAD')

    def git(self, *args, check=True):
        result = subprocess.run(['git', '-C', str(self.repo), *args], check=check,
                                capture_output=True, text=True)
        return result.stdout.strip()

    def write(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-m', message)

    def upstream_commit(self, name='android/dns.txt', content='improved DNS\n'):
        self.git('switch', 'upstream')
        self.write(name, content)
        self.commit('upstream improvement')
        upstream = self.git('rev-parse', 'HEAD')
        self.git('switch', 'main')
        return upstream

    def test_no_update_does_not_create_commit(self):
        result = inherit.prepare(self.repo, 'upstream')
        self.assertFalse(result['changed'])
        self.assertEqual(result['candidate'], self.base)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)

    def test_dns_merge_preserves_local_extension_and_both_parents(self):
        upstream = self.upstream_commit()
        result = inherit.prepare(self.repo, 'upstream')
        self.assertTrue(result['changed'])
        self.assertTrue(result['source_changed'])
        self.assertEqual((self.repo / 'android/dns.txt').read_text(), 'improved DNS\n')
        self.assertEqual((self.repo / 'scripts/taild/feature.txt').read_text(), 'local analytics\n')
        self.assertEqual(self.git('show', '-s', '--format=%P', 'HEAD').split(),
                         [self.base, upstream])

    def test_core_pin_update_is_inherited(self):
        original = (self.repo / 'go.mod').read_text()
        self.upstream_commit('go.mod', original.replace('v1.2.3', 'v1.2.4'))
        result = inherit.prepare(self.repo, 'upstream')
        self.assertTrue(result['source_changed'])
        self.assertIn('v1.2.4', (self.repo / 'go.mod').read_text())

    def test_conflict_fails_without_pushing_or_resetting_main(self):
        self.write('android/dns.txt', 'local DNS\n')
        self.commit('local DNS change')
        before = self.git('rev-parse', 'HEAD')
        self.upstream_commit()
        with self.assertRaises(inherit.InheritanceError):
            inherit.prepare(self.repo, 'upstream')
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertIn('android/dns.txt', self.git('diff', '--name-only', '--diff-filter=U'))

    def test_dirty_checkout_is_not_modified(self):
        self.upstream_commit()
        self.write('android/dns.txt', 'unsaved\n')
        with self.assertRaises(inherit.InheritanceError):
            inherit.prepare(self.repo, 'upstream')
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)
        self.assertEqual((self.repo / 'android/dns.txt').read_text(), 'unsaved\n')

    def reviewed_conflict(self):
        common = self.git('rev-parse', 'HEAD:android/dns.txt')
        upstream = self.upstream_commit()
        theirs = self.git('rev-parse', upstream + ':android/dns.txt')
        self.write('android/dns.txt', 'reviewed local and upstream DNS\n')
        self.commit('reviewed reconciliation')
        ours = self.git('rev-parse', 'HEAD:android/dns.txt')
        record = {upstream: {'android/dns.txt': (common, ours, theirs)}}
        return upstream, record

    def test_exact_reviewed_reconciliation_preserves_both_parents(self):
        upstream, record = self.reviewed_conflict()
        before = self.git('rev-parse', 'HEAD')
        with patch.object(inherit, 'REVIEWED_RECONCILIATIONS', record):
            result = inherit.prepare(self.repo, 'upstream')
        self.assertTrue(result['changed'])
        self.assertEqual(self.git('show', '-s', '--format=%P', 'HEAD').split(),
                         [before, upstream])
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual((self.repo / 'android/dns.txt').read_text(),
                         'reviewed local and upstream DNS\n')

    def test_changed_prepared_blob_rejects_reviewed_reconciliation(self):
        _, record = self.reviewed_conflict()
        self.write('android/dns.txt', 'unreviewed change\n')
        self.commit('changed preparation')
        before = self.git('rev-parse', 'HEAD')
        with patch.object(inherit, 'REVIEWED_RECONCILIATIONS', record):
            with self.assertRaisesRegex(inherit.InheritanceError, 'exact reviewed'):
                inherit.prepare(self.repo, 'upstream')
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertIn('android/dns.txt', self.git('diff', '--name-only', '--diff-filter=U'))

    def test_extra_conflict_rejects_entire_reconciliation_before_changes(self):
        upstream, record = self.reviewed_conflict()
        self.write('android/extra.txt', 'local\n')
        self.commit('local extra')
        before = self.git('rev-parse', 'HEAD')
        self.git('switch', 'upstream')
        self.write('android/extra.txt', 'upstream\n')
        self.commit('upstream extra')
        updated = self.git('rev-parse', 'HEAD')
        self.git('switch', 'main')
        record[updated] = record.pop(upstream)
        with patch.object(inherit, 'REVIEWED_RECONCILIATIONS', record):
            with self.assertRaisesRegex(inherit.InheritanceError, 'exact reviewed'):
                inherit.prepare(self.repo, 'upstream')
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertEqual(set(self.git('diff', '--name-only', '--diff-filter=U').splitlines()),
                         {'android/dns.txt', 'android/extra.txt'})

    def test_inconsistent_core_pin_is_rejected_even_without_update(self):
        text = (self.repo / 'go.mod').read_text()
        self.write('go.mod', text.replace('require tailscale.com v1.2.3',
                                         'require tailscale.com v1.2.9'))
        self.commit('bad local pin')
        with self.assertRaises(inherit.InheritanceError):
            inherit.prepare(self.repo, 'upstream')

    def test_new_inherited_workflow_requires_review(self):
        self.upstream_commit('.github/workflows/new-release.yml', 'name: New release\n')
        with self.assertRaises(inherit.InheritanceError):
            inherit.prepare(self.repo, 'upstream')
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)

    def test_docs_only_merge_does_not_require_native_rebuild(self):
        self.upstream_commit('docs/notes.md', 'Documentation correction\n')
        result = inherit.prepare(self.repo, 'upstream')
        self.assertTrue(result['changed'])
        self.assertFalse(result['source_changed'])

    def test_exact_checked_bundle_can_be_promoted_without_running_candidate_code(self):
        self.upstream_commit()
        result = inherit.prepare(self.repo, 'upstream')
        bundle = self.repo / 'candidate.bundle'
        self.git('bundle', 'create', str(bundle), 'HEAD')
        target = self.repo / 'published.git'
        self.git('init', '--bare', str(target))
        self.git('push', str(target), self.base + ':refs/heads/main')
        checkout = self.repo / 'promotion'
        self.git('clone', '--branch', 'main', str(target), str(checkout))
        subprocess.run(['git', '-C', str(checkout), 'bundle', 'verify', str(bundle)],
                       check=True, capture_output=True)
        subprocess.run(['git', '-C', str(checkout), 'fetch', str(bundle),
                        'HEAD:refs/heads/checked-candidate'], check=True, capture_output=True)
        candidate = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse',
                                             'checked-candidate'], text=True).strip()
        self.assertEqual(candidate, result['candidate'])
        subprocess.run(['git', '-C', str(checkout), 'push', 'origin',
                        candidate + ':refs/heads/main'], check=True, capture_output=True)
        self.assertEqual(self.git('--git-dir=' + str(target), 'rev-parse', 'main'), candidate)

    def test_normal_push_rejects_a_concurrent_main_change(self):
        self.upstream_commit()
        result = inherit.prepare(self.repo, 'upstream')
        target = self.repo / 'published.git'
        self.git('init', '--bare', str(target))
        self.git('push', str(target), self.base + ':refs/heads/main')
        self.git('switch', '-c', 'concurrent', self.base)
        self.write('other.txt', 'concurrent owner change\n')
        self.git('add', 'other.txt')
        self.git('commit', '-m', 'concurrent owner change')
        concurrent = self.git('rev-parse', 'HEAD')
        self.git('push', str(target), concurrent + ':refs/heads/main')
        push = subprocess.run(['git', '-C', str(self.repo), 'push', str(target),
                               result['candidate'] + ':refs/heads/main'], capture_output=True)
        self.assertNotEqual(push.returncode, 0)
        self.assertEqual(self.git('--git-dir=' + str(target), 'rev-parse', 'main'), concurrent)


if __name__ == '__main__':
    unittest.main()
