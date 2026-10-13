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
