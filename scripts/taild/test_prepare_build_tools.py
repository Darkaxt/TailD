"""The alternate official download route must retain the exact asset contract."""
import json
import unittest
from unittest.mock import patch
from prepare_build_tools import release_asset


class BuildToolAssetTests(unittest.TestCase):
    def metadata(self, **changes):
        asset = dict(id=17, name='gradle-9.8.2-bin.zip', size=100, digest='sha256:' + 'a' * 64)
        asset.update(changes)
        return json.dumps(dict(tag_name='v9.8.2', draft=False, assets=[asset]))

    def test_exact_source_checksum(self):
        with patch('prepare_build_tools.subprocess.check_output', return_value=self.metadata()):
            asset, digest = release_asset('gradle/gradle-distributions', 'v9.8.2', 'gradle-9.8.2-bin.zip', 'a' * 64)
        self.assertEqual((asset['id'], digest), (17, 'a' * 64))

    def test_wrong_or_missing_digest_rejected(self):
        for digest in ('sha256:' + 'b' * 64, None, ''):
            with self.subTest(digest=digest), patch('prepare_build_tools.subprocess.check_output', return_value=self.metadata(digest=digest)):
                with self.assertRaises((AssertionError, TypeError)):
                    release_asset('gradle/gradle-distributions', 'v9.8.2', 'gradle-9.8.2-bin.zip', 'a' * 64)

    def test_wrong_asset_rejected(self):
        with patch('prepare_build_tools.subprocess.check_output', return_value=self.metadata(name='other.zip')):
            with self.assertRaises(AssertionError):
                release_asset('gradle/gradle-distributions', 'v9.8.2', 'gradle-9.8.2-bin.zip')
