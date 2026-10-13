"""Narrow workflow authority contracts; real SSH/CI verifies the external boundary."""
from pathlib import Path
import unittest


class InheritanceAuthorityTest(unittest.TestCase):
    def setUp(self):
        self.workflow=(Path(__file__).resolve().parents[2]/'.github/workflows/taild-inherit.yml').read_text()
        self.verify,self.promote=self.workflow.split('\n  promote:\n',1)

    def test_workflow_capable_key_is_repository_scoped_to_the_write_job(self):
        key='ssh-key: ${{ secrets.TAILD_INHERITANCE_SSH_KEY }}'
        self.assertNotIn(key,self.verify)
        self.assertIn(key,self.promote)
        self.assertRegex(self.promote,r'permissions:\s+contents: read\s+actions: read')
        self.assertNotIn('contents: write',self.promote)

    def test_manual_identity_probe_is_distinct_from_upstream_promotion(self):
        self.assertIn('verify_write_identity:',self.workflow)
        self.assertIn('taild-auth-check-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}',self.promote)
        self.assertIn('git push origin "$probe:$ref"',self.promote)
        self.assertIn('git push origin ":$ref"',self.promote)
        self.assertIn("if: needs.verify.outputs.changed == 'true'",self.promote)
        self.assertIn('test "$(git rev-parse origin/main)" = "$BASE"',self.promote)
        self.assertIn('test "$(git show -s --format=%P "$CANDIDATE")" = "$BASE $UPSTREAM"',self.promote)
        self.assertNotIn('--force',self.promote)
