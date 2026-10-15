import contextlib
import importlib
import importlib.util
import io
import os
import unittest
from unittest.mock import patch
import uuid


class CredentialTest(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('credentials'), 'Secure product credential flow missing')
        return importlib.import_module('credentials')

    @unittest.skipUnless(os.name == 'nt', 'Native per-user Windows credential vault')
    def test_native_vault_replace_read_remove_and_no_plaintext_file(self):
        module=self.module()
        target='TailD/test/'+str(uuid.uuid4())
        vault=module.CredentialStore(target)
        try:
            self.assertIsNone(vault.read())
            vault.replace('synthetic-read-token')
            self.assertEqual(vault.read(),'synthetic-read-token')
            vault.replace('replacement-read-token')
            self.assertEqual(vault.read(),'replacement-read-token')
            self.assertNotIn('token',repr(vault))
        finally:
            vault.remove()
        self.assertIsNone(vault.read())

    def test_interactive_entry_is_non_echoed_and_not_recovered_from_environment(self):
        module=self.module()
        with patch.dict(os.environ, {'CONTROLD_READ_TOKEN':'must-not-recover'}), \
             patch.object(module.getpass,'getpass',return_value='fresh-read-token') as entry:
            self.assertEqual(module.prompt_read_token(),'fresh-read-token')
        entry.assert_called_once()

    def test_cli_status_is_secret_free_and_remove_does_not_contact_provider(self):
        module=self.module()
        class Vault:
            removed=False
            def read(self): return 'synthetic-token'
            def remove(self): self.removed=True
        vault=Vault()
        out=io.StringIO()
        with patch.object(module,'CredentialStore',return_value=vault),contextlib.redirect_stdout(out):
            self.assertEqual(module.main(['status']),0)
            self.assertEqual(module.main(['remove']),0)
        self.assertTrue(vault.removed)
        self.assertNotIn('synthetic-token',out.getvalue())

    def test_control_and_blank_credentials_rejected(self):
        module=self.module()
        for token in ('', 'x\r\nAuthorization: secret'):
            with patch.object(module.getpass,'getpass',return_value=token):
                with self.assertRaises(module.CredentialError): module.prompt_read_token()

    def test_noninteractive_getpass_warning_cannot_fall_back_to_echo(self):
        module=self.module()
        def unavailable(*args):
            import warnings
            warnings.warn('Would echo',module.getpass.GetPassWarning)
            self.fail('Secure prompt allowed echoed fallback')
        with patch.object(module.getpass,'getpass',side_effect=unavailable):
            with self.assertRaises(module.CredentialError): module.prompt_read_token()

    def test_write_registration_requires_explicit_confirmation_and_target(self):
        module=self.module()
        self.assertNotEqual(module.WRITE_TARGET,module.TARGET)
        class Vault:
            token=None
            def replace(self,token): self.token=token
        vault=Vault()
        output=io.StringIO()
        errors=io.StringIO()
        with patch.object(module,'CredentialStore',return_value=vault) as create, \
             patch.object(module.sys,'stdin',io.StringIO('synthetic-write-token\n')), \
             contextlib.redirect_stdout(output),contextlib.redirect_stderr(errors):
            self.assertEqual(module.main(['set','--permission','write','--token-stdin']),1)
            create.assert_not_called()
            self.assertEqual(module.main(['set','--permission','write',
                '--confirm-write-access','--token-stdin']),0)
            create.assert_called_once_with(module.WRITE_TARGET)
        self.assertEqual(vault.token,'synthetic-write-token')
        self.assertNotIn('synthetic-write-token',output.getvalue()+errors.getvalue())

    def test_read_stays_default_and_stdin_rejects_multiline_without_echo(self):
        module=self.module()
        class Vault:
            token=None
            def replace(self,token): self.token=token
        vault=Vault()
        out=io.StringIO()
        err=io.StringIO()
        with patch.object(module,'CredentialStore',return_value=vault) as create, \
             patch.object(module.sys,'stdin',io.StringIO('synthetic-read-token\n')), \
             contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            self.assertEqual(module.main(['set','--confirm-read-only','--token-stdin']),0)
            create.assert_called_once_with(module.TARGET)
        self.assertEqual(vault.token,'synthetic-read-token')
        with patch.object(module,'CredentialStore',return_value=vault), \
             patch.object(module.sys,'stdin',io.StringIO('secret-one\nsecret-two\n')), \
             contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            self.assertEqual(module.main(['set','--confirm-read-only','--token-stdin']),1)
        self.assertEqual(vault.token,'synthetic-read-token')
        self.assertNotIn('secret-one',out.getvalue()+err.getvalue())
        self.assertNotIn('secret-two',out.getvalue()+err.getvalue())

    @unittest.skipUnless(os.name == 'nt', 'Native per-user Windows credential vault')
    def test_write_target_can_be_selected_without_mutating_existing_credentials(self):
        module=self.module()
        vault=module.CredentialStore(module.WRITE_TARGET)
        self.assertEqual(vault.target,module.WRITE_TARGET)
        self.assertEqual(module.CredentialStore().target,module.TARGET)
