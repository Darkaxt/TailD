"""Offline country asset provenance and projected geometry contract."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class AndroidCountryMapContract(unittest.TestCase):
    def test_offline_shapes_match_pinned_topology_and_fit_native_viewport(self):
        data = json.loads((ROOT / 'android/src/main/assets/taild-world-map.json').read_text())
        topology = (ROOT / 'desktop/src/portmaster/world-50m.json').read_bytes()
        self.assertEqual(data['source_sha256'], hashlib.sha256(topology).hexdigest())
        self.assertEqual((data['schema'], data['width'], data['height']), (1, 1000, 500))
        self.assertEqual(len(data['countries']), 189)
        codes = {country['code'] for country in data['countries']}
        self.assertTrue({'US', 'DE', 'RO', 'JP', 'AU'}.issubset(codes))
        self.assertNotIn('AQ', codes)
        for country in data['countries']:
            with self.subTest(country=country['code']):
                path = country['path']
                self.assertTrue(path.startswith('M') and path.endswith('Z'))
                self.assertFalse(re.sub(r'[MLZ0-9.,-]', '', path))
                points = [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', path)]
                self.assertEqual(len(points) % 2, 0)
                self.assertTrue(all(7.99 <= x <= 992.01 for x in points[::2]))
                self.assertTrue(all(7.99 <= y <= 492.01 for y in points[1::2]))


if __name__ == '__main__':
    unittest.main()
