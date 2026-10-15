"""Minimal overlay identity and inherited-source preservation contracts."""
import json
import os
from pathlib import Path
import unittest
import uuid
import core_overlay
import core_manifest


class CoreOverlayTest(unittest.TestCase):
    def test_reviewed_build_pins_match_inherited_module(self):
        root=Path(__file__).resolve().parents[2]
        replace=next(line for line in (root/'go.mod').read_text().splitlines()
                     if line.startswith('replace tailscale.com => '))
        module=replace.split()[-1]
        self.assertTrue(module.endswith('-'+core_overlay.PIN),'Inherited core advanced without overlay review')
        self.assertTrue(core_manifest.CORE.startswith(core_overlay.PIN))
        self.assertEqual(core_manifest.CORE_MODULE,module)
        self.assertIn('github.com/Darkaxt/tailscale '+module+' '+core_manifest.CORE_SUM,(root/'go.sum').read_text().splitlines())
        self.assertIn("$commit='"+core_manifest.CORE+"'",(root/'scripts/taild/build_connectivity.ps1').read_text())

    def test_exact_pin_branding_and_channel_overlay_without_source_mutation(self):
        core=os.environ.get('TAILD_CORE_TEST_SOURCE')
        if not core:self.skipTest('Exact downloaded core required for this build integration check')
        root=Path(os.environ['TAILD_PACKAGE_TEST_OUTPUT'])/uuid.uuid4().hex
        before={name:(Path(core)/name).read_bytes() for name in core_overlay.SOURCE_FILES}
        overlay=core_overlay.create(Path(core),root)
        replacements=json.loads(overlay.read_text())['Replace']
        self.assertEqual(len(replacements),len(core_overlay.SOURCE_FILES)+3)
        updater=Path(replacements[str(Path(core)/'clientupdate/taildnsupdate/start_windows.go')]).read_text()
        self.assertIn('TailD.Setup.exe',updater)
        self.assertNotIn('Darkaxt/tailscale/releases',updater)
        feature=Path(replacements[str(Path(core)/'feature/clientupdate/clientupdate.go')]).read_text()
        self.assertIn('"-taild."',feature)
        self.assertNotIn('"-taildns."',feature)
        tray=Path(replacements[str(Path(core)/'client/systray/systray.go')]).read_text()
        self.assertIn('About TailD ',tray)
        self.assertIn('https://github.com/Darkaxt/TailD',tray)
        main=Path(replacements[str(Path(core)/'cmd/taildns-ipn/main_windows.go')]).read_text()
        self.assertIn('configureDesktopAction()',main)
        desktop=Path(replacements[str(Path(core)/'cmd/taildns-ipn/taild_desktop_windows.go')]).read_text()
        self.assertIn('systray.SetOnTapped(',desktop)
        self.assertNotIn('systray.SetOnSecondaryTapped(',desktop)
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
