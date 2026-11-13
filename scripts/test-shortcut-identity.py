"""Verify launcher shortcuts address this fork while retaining implementation classes."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ANDROID = '{http://schemas.android.com/apk/res/android}'


def verify(shortcuts, manifest, strings, application_id):
    activity = manifest.find("./application/activity[@" + ANDROID + "name='AutomationActivity']")
    assert activity is not None, 'Missing shortcut activity'
    actions = {a.get(ANDROID + 'name') for a in activity.findall('./intent-filter/action')}
    expected = {application_id + '.CONNECT_VPN', application_id + '.DISCONNECT_VPN'}
    declared = {a.replace('${applicationId}', application_id) for a in actions}
    assert declared == expected, 'Shortcut activity actions target another package'
    intents = shortcuts.findall('./shortcut/intent')
    assert len(intents) == 2
    assert {i.get(ANDROID + 'action') for i in intents} == expected
    for intent in intents:
        assert intent.get(ANDROID + 'targetPackage') == application_id, 'Wrong shortcut package'
        assert intent.get(ANDROID + 'targetClass') == 'com.tailscale.ipn.AutomationActivity'
    labels = {s.get('name'): s.text for s in strings.findall('string')}
    assert labels['shortcut_connect_long'] == 'Connect to TailDNS'
    assert labels['shortcut_disconnect_long'] == 'Disconnect from TailDNS'


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    build = (root / 'android/build.gradle.kts').read_text(encoding='utf-8')
    ids = re.findall(r'^\s*applicationId = "([^"]+)"$', build, re.M)
    assert ids == ['io.github.darkaxt.taildns']
    verify(ET.parse(root / 'android/src/main/res/xml/shortcuts.xml').getroot(),
           ET.parse(root / 'android/src/main/AndroidManifest.xml').getroot(),
           ET.parse(root / 'android/src/main/res/values/strings.xml').getroot(), ids[0])
    print('TailDNS launcher package, actions, class and branding verified.')
