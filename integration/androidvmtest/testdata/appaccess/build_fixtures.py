"""Build three small real-UID network fixtures and a shell-only policy oracle."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--java', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--keystore', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parent
    tools = args.sdk / 'build-tools/35.0.0'
    platform = args.sdk / 'platforms/android-35/android.jar'
    def run(*command):
        subprocess.run([str(x) for x in command], check=True)
    classes, dex = out / 'classes', out / 'dex'
    classes.mkdir(); dex.mkdir()
    run(args.java / 'bin/javac.exe', '--release', '8', '-cp', platform, '-d', classes,
        source / 'ProbeReceiver.java', source / 'PolicyControl.java', source / 'TrafficReceiver.java')
    jar = out / 'fixture.jar'
    with zipfile.ZipFile(jar, 'w') as archive:
        for path in classes.rglob('*.class'):
            archive.write(path, path.relative_to(classes).as_posix())
    run(tools / 'd8.bat', '--lib', platform, '--min-api', '33', '--output', dex, jar)
    if not args.keystore.exists():
        args.keystore.parent.mkdir(parents=True, exist_ok=True)
        run(args.java / 'bin/keytool.exe', '-genkeypair', '-keystore', args.keystore,
            '-storepass', 'owned-fixture', '-keypass', 'owned-fixture', '-alias', 'fixture',
            '-keyalg', 'RSA', '-keysize', '2048', '-validity', '3650', '-dname', 'CN=TailD isolated test fixture')
    inventory = []
    for suffix, label, shared in [('one', 'One', True), ('two', 'Two', True), ('other', 'Other', False)]:
        package = 'io.github.darkaxt.taild.fixture.' + suffix
        shared_attribute = 'android:sharedUserId="io.github.darkaxt.taild.fixture.shared"' if shared else ''
        manifest = out / (suffix + '-manifest.xml')
        manifest.write_text(f'''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{package}" {shared_attribute} android:versionCode="1" android:versionName="1.0">
<uses-sdk android:minSdkVersion="33" android:targetSdkVersion="35"/>
<uses-permission android:name="android.permission.INTERNET"/>
<application android:label="TailD F0 {label}" android:debuggable="true" android:usesCleartextTraffic="true" android:allowBackup="false">
<receiver android:name="io.github.darkaxt.taild.fixture.ProbeReceiver" android:exported="true"/>
<receiver android:name="io.github.darkaxt.taild.fixture.TrafficReceiver" android:exported="true"/>
</application></manifest>''', encoding='utf-8')
        unsigned, aligned, apk = [out / (suffix + ending) for ending in ['-unsigned.apk', '-aligned.apk', '.apk']]
        run(tools / 'aapt2.exe', 'link', '-I', platform, '--manifest', manifest, '-o', unsigned)
        with zipfile.ZipFile(unsigned, 'a') as archive:
            archive.write(dex / 'classes.dex', 'classes.dex')
        run(tools / 'zipalign.exe', '-f', '4', unsigned, aligned)
        run(tools / 'apksigner.bat', 'sign', '--ks', args.keystore, '--ks-pass', 'pass:owned-fixture',
            '--key-pass', 'pass:owned-fixture', '--out', apk, aligned)
        run(tools / 'apksigner.bat', 'verify', '--verbose', '--print-certs', apk)
        inventory.append({'package': package, 'shared_uid_group': shared,
                          'apk': str(apk), 'sha256': hashlib.sha256(apk.read_bytes()).hexdigest()})
    receipt = {'schema': 1, 'fixtures': inventory,
               'policy_dex_sha256': hashlib.sha256((dex / 'classes.dex').read_bytes()).hexdigest(),
               'sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in [source / 'ProbeReceiver.java', source / 'PolicyControl.java', source / 'TrafficReceiver.java']}}
    (out / 'fixtures.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps({'inventory': str(out / 'fixtures.json'), 'policy_dex': str(dex / 'classes.dex')}))


if __name__ == '__main__':
    main()
