"""Resolve owned core pins and an exact reviewed interface conflict; fail closed."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess


INTERFACE_PATH = 'libtailscale/interfaces.go'
INTERFACE_BLOBS = {
    '1': '8adbcc188a0b80384e7b6b9b84d9e19f4aee5588',
    '2': 'bf25cad6d862f80dcea530075ded05ce9b6806f5',
    '3': 'ac702a03c6aea91edbca70cc390fa2e1848e11b6',
}

# Reviewed canonical DNS lifecycle migration, composed with the profile-owned
# TailDNS controls. Whole-file inputs are immutable; unknown changes fail closed.
DNS_UPSTREAM = '2994f80c7f2e5d6b2ec6bb47c06b1c7a3a949d30'
DNS_ROOT = 'android/src/main/java/com/tailscale/ipn/ui/'
DNS_VIEW = DNS_ROOT + 'view/DNSSettingsView.kt'
DNS_MODEL = DNS_ROOT + 'viewModel/DNSSettingsViewModel.kt'
DNS_SOURCE = DNS_ROOT + 'dataSource/DNSSettingsDataSource.kt'
DNS_TEST = 'android/src/test/kotlin/com/tailscale/ipn/ui/viewModel/DNSSettingsViewModelTest.kt'
DNS_SOURCE_BLOB = 'bdbb8484ed9771dd15ddaf543c4af1c2376f50fe'
DNS_BLOBS = {
    DNS_VIEW: {'1': '75e2f4769a2b5e882e52747ed2264f41ed505307',
               '2': 'a1559e4dd74f1b30da95caf9a3e8729c0d5b7115',
               '3': 'e9f2d7be21e78908e4f8afdddc632c1d70c928f5'},
    DNS_MODEL: {'1': 'e770cfdaac5c222b275457c0d492fd941403aca0',
                '2': 'e06e635ab84e6cff21f18658863cabd95b4c5602',
                '3': 'be6307b5f6ee8c222c4557139be9bbb73981d2cc'},
}
DNS_PAYLOADS = {
    DNS_SOURCE: '5be51c22e0f3be891ab496ecdebaa3d5c363c7876245155fdb6cb8201ad01ce9',
    DNS_MODEL: '6a38a0f941ced86bcd716156f198ccb4f1a3cd5b5df5340027dda6bd7a657a74',
    DNS_VIEW: '8a7775b993ea277d32b654a358610a7266ad84605e69d8352e9b46319b4fa106',
    DNS_TEST: '5d5df45dfc51b6aa8aaba38e440d8837e273149dc6cb471c7ea636c42d84a4c2',
}
SHORTCUT = 'android/src/main/res/xml/shortcuts.xml'
MANIFEST = 'android/src/main/AndroidManifest.xml'
STRINGS = 'android/src/main/res/values/strings.xml'
SHORTCUT_BLOBS = {
    SHORTCUT: '549e0aaa21c3ac96e5e12b18e3192334394b5305',
    MANIFEST: '4cd639930fbc5396439df7046f14fc8dbc85977b',
    STRINGS: '90a21dc4adb116c1013f84b94cc480b57ae4d3a0',
}


def resolve_shortcuts(blobs, texts):
    if blobs != SHORTCUT_BLOBS or set(texts) != set(SHORTCUT_BLOBS):
        raise ValueError('Unreviewed launcher shortcut inputs')
    result = dict(texts)
    replacements = {
        SHORTCUT: [('android:targetPackage="com.tailscale.ipn"',
                    'android:targetPackage="io.github.darkaxt.taildns"', 2),
                   ('android:action="com.tailscale.ipn.CONNECT_VPN"',
                    'android:action="io.github.darkaxt.taildns.CONNECT_VPN"', 1),
                   ('android:action="com.tailscale.ipn.DISCONNECT_VPN"',
                    'android:action="io.github.darkaxt.taildns.DISCONNECT_VPN"', 1)],
        MANIFEST: [('android:name="com.tailscale.ipn.CONNECT_VPN"',
                    'android:name="${applicationId}.CONNECT_VPN"', 1),
                   ('android:name="com.tailscale.ipn.DISCONNECT_VPN"',
                    'android:name="${applicationId}.DISCONNECT_VPN"', 1)],
        STRINGS: [('name="shortcut_connect_long">Connect to Tailscale</string>',
                   'name="shortcut_connect_long">Connect to TailDNS</string>', 1),
                  ('name="shortcut_disconnect_long">Disconnect from Tailscale</string>',
                   'name="shortcut_disconnect_long">Disconnect from TailDNS</string>', 1)],
    }
    for name, edits in replacements.items():
        for before, after, count in edits:
            if result[name].count(before) != count:
                raise ValueError('Reviewed launcher shortcut changed shape')
            result[name] = result[name].replace(before, after)
    return result


def resolve_dns(upstream, blobs, companion):
    if upstream != DNS_UPSTREAM or blobs != DNS_BLOBS or companion != DNS_SOURCE_BLOB:
        raise ValueError('Unreviewed DNS migration inputs')
    payload_root = Path(__file__).resolve().parent / 'upstream-reconciliations/dns-settings'
    resolved = {}
    for name, digest in DNS_PAYLOADS.items():
        payload = payload_root / Path(name).name
        if payload.is_symlink():
            raise ValueError('DNS payload is a symlink')
        data = payload.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Reviewed DNS payload changed')
        resolved[name] = data.decode('utf-8')
    return resolved


def validate_paths(paths):
    if paths not in ({'go.mod', 'go.sum'}, {'go.mod', 'go.sum', INTERFACE_PATH},
                     {'go.mod', 'go.sum', *DNS_BLOBS}):
        raise ValueError('Unreviewed merge conflict paths')


def resolve_interface(blobs, merged):
    if blobs != INTERFACE_BLOBS:
        raise ValueError('Unreviewed interface conflict blobs')
    legacy = ('\t// GetPlatformDNSConfig gets a string representation of the current DNS\n'
              '\t// configuration.\n'
              '\tGetPlatformDNSConfig() string\n\n')
    owned = ('\t// ReadPrivateDNSProviderJSON reads the saved hostname and system mode without\n'
             '\t// privileged APIs. SetPrivateDNSObservation registers before the first read.\n'
             '\tReadPrivateDNSProviderJSON() (string, error)\n'
             '\tSetPrivateDNSObservation(enabled bool) error\n\n')
    pattern = r'<<<<<<< HEAD\n' + re.escape(legacy + owned) + r'=======\n>>>>>>> [0-9a-f]{40}\n'
    result, count = re.subn(pattern, lambda _: owned, merged)
    if count != 1 or re.search(r'^(?:<<<<<<< |=======|>>>>>>> |\|\|\|\|\|\|\| )', result, re.M):
        raise ValueError('Reviewed interface conflict changed shape')
    # Keep the already-merged file, including every non-conflicting fork member
    # such as Application.NotifyPrivateDNSChanged. Replace only the exact hunk.
    return result


def resolve(text, path):
    lines = iter(text.splitlines(keepends=True))
    result = []
    for line in lines:
        if not line.startswith('<<<<<<< '):
            if line.startswith(('=======', '>>>>>>> ', '||||||| ')):
                raise ValueError('Unexpected conflict marker')
            result.append(line)
            continue
        ours, theirs = [], []
        for line in lines:
            if line == '=======\n':
                break
            ours.append(line)
        else:
            raise ValueError('Missing conflict separator')
        for line in lines:
            if line.startswith('>>>>>>> '):
                break
            theirs.append(line)
        else:
            raise ValueError('Missing conflict terminator')
        pattern = (r'\s*tailscale\.com v\S+\n' if path == 'go.mod'
                   else r'tailscale\.com v\S+ h1:[A-Za-z0-9+/=]+\n')
        if path == 'go.mod' and (len(ours) != 1 or len(theirs) != 1):
            raise ValueError('Core requirement conflict changed shape')
        if not all(re.fullmatch(pattern, item) for item in ours + theirs):
            raise ValueError('Conflict includes changes outside the owned core pin')
        result.extend(ours)
    return ''.join(result)


def git(*args):
    return subprocess.check_output(['git', *args], text=True, encoding='utf-8')


def reconcile(upstream):
    if not re.fullmatch(r'[0-9a-f]{40}', upstream):
        raise ValueError('Expected immutable upstream revision')
    if git('rev-parse', 'MERGE_HEAD').strip() != upstream:
        raise ValueError('Different upstream merge is active')
    stages = {}
    for entry in git('ls-files', '--unmerged', '-z').split('\0'):
        if not entry:
            continue
        metadata, path = entry.split('\t', 1)
        mode, blob, stage = metadata.split()
        if mode != '100644':
            raise ValueError('Unreviewed conflict file mode')
        stages.setdefault(path, {})[stage] = blob
    validate_paths(set(stages))
    if any(set(value) != {'1', '2', '3'} for value in stages.values()):
        raise ValueError('Missing conflict stage')
    original = git('show', ':2:go.mod')
    pin = re.findall(r'^\s*tailscale\.com (v\S+)\s*$', original, re.M)
    replacement = re.findall(r'^replace tailscale\.com => github\.com/Darkaxt/tailscale (v\S+)\s*$', original, re.M)
    if len(pin) != 1 or pin != replacement:
        raise ValueError('Expected matching fork-owned core require/replace')
    resolved = {}
    if DNS_VIEW in stages:
        companion = git('ls-files', '-s', '--', DNS_SOURCE).strip()
        if companion != '100644 ' + DNS_SOURCE_BLOB + ' 0\t' + DNS_SOURCE:
            raise ValueError('Unreviewed DNS data source index entry')
        if git('ls-files', '--', DNS_TEST).strip() or Path(DNS_TEST).exists():
            raise ValueError('DNS regression test target already exists')
        resolved.update(resolve_dns(upstream, {p: stages[p] for p in DNS_BLOBS},
                                    DNS_SOURCE_BLOB))
        companions = {}
        for name, blob in SHORTCUT_BLOBS.items():
            if git('ls-files', '-s', '--', name).strip() != '100644 ' + blob + ' 0\t' + name:
                raise ValueError('Unreviewed launcher shortcut index entry')
            companions[name] = git('show', ':0:' + name)
        resolved.update(resolve_shortcuts(SHORTCUT_BLOBS, companions))
    for name in sorted(stages):
        path = Path(name)
        if path.is_symlink():
            raise ValueError('Conflict path is a symlink')
        if name in DNS_BLOBS:
            continue
        if name == INTERFACE_PATH:
            resolved[name] = resolve_interface(stages[name], path.read_text(encoding='utf-8'))
        else:
            resolved[name] = resolve(path.read_text(encoding='utf-8'), name)
    if re.findall(r'^\s*tailscale\.com (v\S+)\s*$', resolved['go.mod'], re.M) != pin:
        raise ValueError('Fork-owned core pin was not preserved')
    if re.findall(r'^replace tailscale\.com => github\.com/Darkaxt/tailscale (v\S+)\s*$', resolved['go.mod'], re.M) != replacement:
        raise ValueError('Fork-owned replacement was not preserved')
    # Validate every conflict before changing either file. The updater then
    # installs the exact reviewed core and runs tidy plus trusted candidate gates.
    for name in resolved:
        if Path(name).is_symlink():
            raise ValueError('Resolution target is a symlink')
    for name, text in resolved.items():
        Path(name).parent.mkdir(parents=True, exist_ok=True)
        Path(name).write_bytes(text.encode('utf-8'))
    subprocess.run(['git', 'add', '--', *sorted(resolved)], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', required=True)
    args = parser.parse_args()
    try:
        reconcile(args.upstream)
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + '\n')
