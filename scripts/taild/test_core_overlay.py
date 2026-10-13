"""Minimal overlay identity and inherited-source preservation contracts."""
import json
import os
from pathlib import Path
import unittest
import uuid
import core_overlay


class CoreOverlayTest(unittest.TestCase):
    def test_exact_pin_branding_and_channel_overlay_without_source_mutation(self):
        core=os.environ.get('TAILD_CORE_TEST_SOURCE')
        if not core:self.skipTest('Exact downloaded core required for this build integration check')
        root=Path(os.environ['TAILD_PACKAGE_TEST_OUTPUT'])/uuid.uuid4().hex
        before={name:(Path(core)/name).read_bytes() for name in core_overlay.SOURCE_FILES}
        overlay=core_overlay.create(Path(core),root)
        replacements=json.loads(overlay.read_text())['Replace']
        self.assertEqual(len(replacements),len(core_overlay.SOURCE_FILES)+1)
        updater=Path(replacements[str(Path(core)/'clientupdate/taildnsupdate/start_windows.go')]).read_text()
        self.assertIn('TailD.Setup.exe',updater)
        self.assertNotIn('Darkaxt/tailscale/releases',updater)
        feature=Path(replacements[str(Path(core)/'feature/clientupdate/clientupdate.go')]).read_text()
        self.assertIn('"-taild."',feature)
        self.assertNotIn('"-taildns."',feature)
        tray=Path(replacements[str(Path(core)/'client/systray/systray.go')]).read_text()
        self.assertIn('About TailD ',tray)
        self.assertIn('https://github.com/Darkaxt/TailD',tray)
        core_installer=Path(replacements[str(Path(core)/'cmd/taildns-installer/install_windows.go')]).read_text()
        self.assertIn('func platformUnmigrate()',core_installer)
        self.assertIn('!original && err == nil',core_installer)
        self.assertIn('runValueName = "TailDNS"',core_installer)
        for name,value in before.items():self.assertEqual((Path(core)/name).read_bytes(),value)

    def test_changed_pin_fails_before_any_output(self):
        root=Path(os.environ['TAILD_PACKAGE_TEST_OUTPUT'])/uuid.uuid4().hex
        source=root/'wrong-core';source.mkdir(parents=True);(source/'VERSION.txt').write_text('1.106.0')
        with self.assertRaisesRegex(ValueError,'pin'):
            core_overlay.create(source,root/'overlay')
        self.assertFalse((root/'overlay').exists())


if __name__=='__main__':unittest.main()
