"""Exercise the real updater merge block with fork policy and exact Git parents."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkflowCompositionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix='workflow-test-', dir=os.environ.get('TAILDNS_WORKFLOW_TEST_ROOT'))
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Synthetic workflow test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        for name in ('reconcile-upstream-core-pin.py', 'test-reconcile-upstream-core-pin.py'):
            self.write('scripts/' + name, (ROOT / 'scripts' / name).read_text(encoding='utf-8'))
        for payload in (ROOT / 'scripts/upstream-reconciliations/dns-settings').glob('*.kt'):
            self.write('scripts/upstream-reconciliations/dns-settings/' + payload.name,
                       payload.read_text(encoding='utf-8'))
        self.workflow = (ROOT / '.github/workflows/upstream-candidate.yml').read_text(encoding='utf-8')
        self.write('.github/workflows/upstream-candidate.yml', self.workflow)
        self.write('.github/workflows/integration-test.yml', 'name: common policy\n')
        self.write('go.mod', 'module example.invalid/test\n\nrequire (\n\ttailscale.com v1.2.2\n'
                   '\tother.example/a v1.0.0\n\tother.example/b v1.0.0\n'
                   '\tother.example/c v1.0.0\n)\n\n'
                   'replace tailscale.com => github.com/Darkaxt/tailscale v1.2.2\n')
        self.write('go.sum', 'github.com/Darkaxt/tailscale v1.2.3-fork h1:Fork=\n'
                   'other.example/module v1.0.0 h1:Other=\n'
                   'tailscale.com v1.2.2 h1:Base=\n')
        self.write('source.go', 'common source\n')
        self.commit('common')
        self.git('branch', 'canonical')
        self.write('.github/workflows/integration-test.yml', 'name: fork policy\n')
        path = self.repo / 'go.mod'
        path.write_text(path.read_text().replace('v1.2.2', 'v1.2.3-fork'), encoding='utf-8', newline='\n')
        self.write('go.sum', 'github.com/Darkaxt/tailscale v1.2.3-fork h1:Fork=\n'
                   'other.example/module v1.0.0 h1:Other=\n')
        self.commit('fork policy and pins')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, encoding='utf-8').strip()

    def write(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-m', message)

    def compose(self, *, source_conflict=False, module_conflict=False, workflow_conflict=True):
        if source_conflict:
            self.write('source.go', 'fork source\n')
            self.commit('fork source change')
        base = self.git('rev-parse', 'HEAD')
        self.git('update-ref', 'refs/remotes/origin/main', base)
        self.git('switch', 'canonical')
        if workflow_conflict:
            self.write('.github/workflows/integration-test.yml', 'name: canonical policy\n')
        if source_conflict:
            self.write('source.go', 'different canonical source\n')
        if module_conflict:
            path = self.repo / 'go.mod'
            path.write_text(path.read_text().replace('tailscale.com v1.2.2', 'tailscale.com v1.2.4', 1), encoding='utf-8', newline='\n')
            self.write('go.sum', 'github.com/Darkaxt/tailscale v1.2.3-fork h1:Fork=\n'
                       'other.example/module v1.0.0 h1:Other=\n'
                       'tailscale.com v1.2.4 h1:Upstream=\n')
        self.write('canonical.feature', 'canonical feature survives\n')
        self.commit('canonical update')
        upstream = self.git('rev-parse', 'HEAD')
        self.git('switch', 'main')
        start = self.workflow.index('          if [[ "$android_changed" == true ]]; then')
        end = self.workflow.index('          if [[ "$core_changed" == true ]]; then', start)
        script = textwrap.dedent(self.workflow[start:end])
        # Use the running test interpreter rather than Windows' python3 app alias.
        script = script.replace('python3 ', shlex.quote(sys.executable.replace('\\', '/')) + ' ')
        shell = Path('C:/Program Files/Git/bin/bash.exe') if os.name == 'nt' else Path(shutil.which('bash'))
        command = self.repo / 'composition.sh'
        command.write_text('set -euo pipefail\n' + script, encoding='utf-8', newline='\n')
        env = os.environ.copy()
        env.update(android_changed='true', android_head=upstream, base='main',
                   GITHUB_STEP_SUMMARY=str(self.repo / 'summary.md'))
        result = subprocess.run([str(shell), str(command)], cwd=self.repo, env=env,
                                capture_output=True, text=True, encoding='utf-8')
        return result, base, upstream

    def assert_promoted(self, result, base, upstream):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git('show', '-s', '--format=%P', 'HEAD').split(), [base, upstream])
        self.assertEqual((self.repo / '.github/workflows/integration-test.yml').read_text(),
                         'name: fork policy\n')
        self.assertEqual((self.repo / 'canonical.feature').read_text(), 'canonical feature survives\n')
        self.assertFalse(self.git('ls-files', '--unmerged'))

    def test_workflow_only_conflict_is_already_resolved_after_policy_restore(self):
        self.assert_promoted(*self.compose())

    def test_clean_merge_keeps_fork_policy_and_both_parents(self):
        self.assert_promoted(*self.compose(workflow_conflict=False))

    def test_owned_core_pin_conflicts_still_use_strict_resolver(self):
        self.assert_promoted(*self.compose(module_conflict=True))
        self.assertIn('tailscale.com v1.2.3-fork', (self.repo / 'go.mod').read_text())
        self.assertNotIn('tailscale.com v1.2.4', (self.repo / 'go.sum').read_text())

    def test_unknown_source_conflict_aborts_without_promoting(self):
        result, base, _ = self.compose(source_conflict=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git('rev-parse', 'HEAD'), base)
        self.assertEqual((self.repo / 'source.go').read_text(), 'fork source\n')
        self.assertFalse(self.git('ls-files', '--unmerged'))


if __name__ == '__main__':
    unittest.main()
