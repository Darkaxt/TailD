"""Pinned SQLite package and before-write frozen runtime contracts."""
import unittest
from unittest.mock import patch
import history
import glasswire
try:import package_sqlite
except ImportError:package_sqlite=None

class SQLitePackageTest(unittest.TestCase):
    def test_unsafe_frozen_runtime_is_rejected_before_history_access(self):
        self.assertIsNotNone(package_sqlite,'Pinned safe SQLite package gate is missing')
        for version in ('3.50.4','3.51.2','unexpected'):
            with self.subTest(version=version),patch('sys.frozen',True,create=True),patch('sqlite3.sqlite_version',version),patch.object(history,'private_directory',side_effect=AssertionError('History touched before runtime guard')):
                with self.assertRaisesRegex(RuntimeError,'unsafe-sqlite-runtime'):history.History('unused')

    def test_exact_frozen_runtime_is_allowed_and_developer_runtime_is_not_replaced(self):
        self.assertIsNotNone(package_sqlite,'Pinned safe SQLite package gate is missing')
        with patch('sys.frozen',True,create=True),patch('sqlite3.sqlite_version','3.54.0'):package_sqlite.require_runtime()
        with patch('sys.frozen',False,create=True),patch('sqlite3.sqlite_version','3.50.4'):package_sqlite.require_runtime()

    def test_unsafe_frozen_reader_fails_before_opening_source(self):
        with patch('sys.frozen',True,create=True),patch('sqlite3.sqlite_version','3.50.4'),patch('sqlite3.connect',side_effect=AssertionError('Unsafe source connection opened')):
            with self.assertRaisesRegex(RuntimeError,'unsafe-sqlite-runtime'):glasswire._connect('unused')

    def test_archive_digest_is_checked_before_zip_or_output_access(self):
        self.assertIsNotNone(package_sqlite,'Pinned safe SQLite package gate is missing')
        with self.assertRaisesRegex(ValueError,'sqlite-archive-digest'):package_sqlite.unpack(b'untrusted')
