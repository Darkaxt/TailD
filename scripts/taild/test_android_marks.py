"""Keep the native integration artwork identical to the Windows reference."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
ATTR = "{http://schemas.android.com/apk/res/android}"


class AndroidIntegrationMarks(unittest.TestCase):
    def test_control_d_preserves_all_official_paths_and_proportions(self):
        source = (ROOT / "desktop/src/brand-mark.ts").read_text(encoding="utf-8")
        expected = re.findall(r'<path d="([^"]+)"', source)
        vector = ET.parse(ROOT / "android/src/main/res/drawable/taild_brand_controld.xml").getroot()
        self.assertEqual((vector.get(ATTR + "viewportWidth"), vector.get(ATTR + "viewportHeight")), ("44", "33"))
        self.assertEqual([path.get(ATTR + "pathData") for path in vector], expected)
        self.assertEqual(len(expected), 4)

    def test_tailscale_preserves_circle_geometry_and_dimmed_dots(self):
        source = (ROOT / "desktop/src/brand-mark.ts").read_text(encoding="utf-8")
        circles = re.findall(r'<circle cx="([^"]+)" cy="([^"]+)" r="([^"]+)"([^>]*)/>', source)
        vector = ET.parse(ROOT / "android/src/main/res/drawable/taild_brand_tailscale.xml").getroot()
        self.assertEqual(len(circles), 9)
        self.assertEqual(len(vector), 9)
        for path, (cx, cy, radius, attributes) in zip(vector, circles):
            start = re.match(r"M([0-9.]+),([0-9.]+)a([0-9.]+),([0-9.]+)", path.get(ATTR + "pathData"))
            self.assertIsNotNone(start)
            x, y, rx, ry = map(float, start.groups())
            self.assertAlmostEqual(x + rx, float(cx), places=5)
            self.assertAlmostEqual(y, float(cy), places=5)
            self.assertEqual((rx, ry), (float(radius), float(radius)))
            self.assertEqual(path.get(ATTR + "fillAlpha", "1"), "0.2" if 'opacity=".2"' in attributes else "1")
            self.assertEqual(path.get(ATTR + "fillColor"), "#FFFFFFFF")


if __name__ == "__main__":
    unittest.main()
