"""Prepare a checked TailDNS merge. This command never fetches or pushes."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


class InheritanceError(RuntimeError):
    pass


# Reviewed typed-navigation reconciliation. Each tuple is the exact common,
# prepared TailD, and upstream blob. Unknown revisions/conflicts still fail.
REVIEWED_RECONCILIATIONS = {
    '298ce62b6f10952590cbe40049adeeb27d99a6d3': {
        'android/src/main/java/com/tailscale/ipn/MainActivity.kt': (
            '456d1567bf323fa19ef2c2b4d73f8987e6e7da1e',
            '600202f848589c2167c0df187f47195f261728bd',
            '725514fb682c9a2df429053c89297ff6409e78b2'),
        'android/src/main/java/com/tailscale/ipn/ui/view/SettingsView.kt': (
            '88ce51a8ad145c3cce68607d519cef15800d76d5',
            'b862c090b91d66dd7be0e94c2bc9f778d9ffac91',
            'db63f0fb1e4e4d881340142ef9a3600afed8decf'),
        'scripts/test-taildns-branding.sh': (
            '1a59fb157881c4afefe93bfa34f41e6aabf863a7',
            '623ff606a32091b5f905b202b86b774d5e16c4c5',
            '34bc9018fa34b05f558be976f5cf458119336696'),
    },
    '3a192a84f81d4eaa2aa2e5adb74f2b9d452ba5de': {
        'android/src/main/java/com/tailscale/ipn/ui/view/PeerDetails.kt': (
            '3d3b3707afa7bb1e649bcf08c7e9137af03818eb',
            'ae878d26615e1847b809b08d8638bc9e3df62492',
            '721782d96f550e6729e8aec3988d12e74b21360b'),
    },
    'c2a979e263b348a7014779476a97b8870b63bf5b': {
        'README.md': (
            '1124d45ece1db5a6169b2c4914f4ca2687bff883',
            'b3a1a985c8b9c0ce4908a9de8321fe59344689ae',
            'dd1cf8efd061971b8af63d3e0bade8c84d70cf6f'),
        'android/src/main/java/com/tailscale/ipn/ui/view/Avatar.kt': (
            '7c4fb53e253ad061c228d771455411d438a54926',
            '024ae59655b24f6398927f4ac1a7d49ef3f54789',
            '74b646fbd28520aa29dc9a41adf42b6fbd456100'),
        'android/src/main/java/com/tailscale/ipn/ui/view/SettingsView.kt': (
            'f410cec120335474536fe77ce72afe3b11c408e3',
            'b862c090b91d66dd7be0e94c2bc9f778d9ffac91',
            '88ce51a8ad145c3cce68607d519cef15800d76d5'),
    },
    'fb92cde78c48c1c2536a03706431d1d23a107791': {
        'android/src/main/java/com/tailscale/ipn/MainActivity.kt': (
            '4a7e3350722b15134e904335100e57d9315494d7',
            '3b373d527f0d820bc180ce9f832215593385b2b9',
            'd403f3c8773997da1d0e8078c073a4c8176384a9'),
        'android/src/main/java/com/tailscale/ipn/ui/util/DeepLinkNavigator.kt': (
            'ea988f58c6a766adbb3458d0bc95e22e4461549c',
            'bf2b2d125c596120ed96c38c056f166c49864f0d',
            '9f2030f960be0aff5a432935a7f26ca9447a0cc1'),
        'android/src/main/java/com/tailscale/ipn/ui/view/SearchView.kt': (
            'ae0c2af1f40e8e53c55448ec1d949a4cd4d577e7',
            'fd4e056bdf966745a00560ec6c375ad7abfeddd0',
            '9e35065bf3a25567c89f88845c26d7cc7ec8d3bd'),
    },
}

SETTINGS_UPSTREAM = '298ce62b6f10952590cbe40049adeeb27d99a6d3'
SETTINGS_PAYLOADS = {
    'android/src/main/java/com/tailscale/ipn/MainActivity.kt':
        ('MainActivity.kt', '76bbaeda3df98ce898a6a91e3b9a0edfb1b337378e0b070fe511bcb3411e85e2'),
    'android/src/main/java/com/tailscale/ipn/ui/view/SettingsView.kt':
        ('SettingsView.kt', '05d52ac58bdc0ff11d24bda0482c4a1fa679a9fc305091e59114bafc16f332e4'),
    'scripts/test-taildns-branding.sh':
        ('test-taildns-branding.sh', '847c6931fd4d0b734ecf76bcaf255e41376c242a747b8c3d971d1fc5c359ba83'),
}
SETTINGS_COMPANIONS = {
    'android/src/main/java/com/tailscale/ipn/taild/TailDTailscaleView.kt': (
        'e0a2fbeccb7cd3698bbd9ac12255e8fcfed2e4e9',
        '168820ef66812532dd1c4b17204ddaad438b951b672057ef9a5fccd45ff6cde7'),
    'android/src/main/res/values/strings.xml': (
        '04985a6918e3ec34c0f5056d0b91eaee45046b5e',
        '50e57773e2e9b65d1943e0e2402612b8caed0d0eebb747b9f889df009594934f'),
    'scripts/test-shortcut-identity.py': (
        '241b145916156d674d5f3ffd7885cf1d393f5be6',
        '1768e06beca76a2dd5cc7802265cb38687107cd95c2e70880da09a715f446523'),
}


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise InheritanceError('Reviewed settings companion changed')
    return text.replace(old, new)


def settings_companion(path, text):
    if path.endswith('TailDTailscaleView.kt'):
        text = replace_once(text, 'import com.tailscale.ipn.ui.Links\n',
                            'import com.tailscale.ipn.ui.Links\n'
                            'import com.tailscale.ipn.ui.dataSource.SettingsDataSourceImpl\n')
        return replace_once(text,
            '              4 -> SettingsView(settingsNav, appViewModel = appViewModel, embedded = true)',
            '              4 -> {\n'
            '                val settingsDataSource = remember { SettingsDataSourceImpl() }\n'
            '                SettingsView(\n'
            '                    settingsNav = settingsNav,\n'
            '                    dataSource = settingsDataSource,\n'
            '                    mainViewModel = viewModel,\n'
            '                    appViewModel = appViewModel,\n'
            '                    embedded = true,\n'
            '                )\n'
            '              }')
    text = replace_once(text, 'Connect to TailDNS', 'Connect to TailD')
    text = replace_once(text, 'Disconnect from TailDNS', 'Disconnect from TailD')
    if path.endswith('test-shortcut-identity.py'):
        text = replace_once(text, 'TailDNS launcher package', 'TailD launcher package')
    return text


def settings_outputs(repo):
    """Validate all reviewed inputs and outputs before changing the merge tree."""
    repo = Path(repo).resolve()
    outputs = {}
    payload_root = Path(__file__).parent / 'inheritance-resolutions' / '20261113'
    for path, (name, digest) in SETTINGS_PAYLOADS.items():
        data = (payload_root / name).read_bytes().replace(b'\r\n', b'\n')
        if hashlib.sha256(data).hexdigest() != digest:
            raise InheritanceError('Reviewed settings payload changed: ' + path)
        outputs[path] = data
    for path, (blob, digest) in SETTINGS_COMPANIONS.items():
        entries = git(repo, 'ls-files', '--stage', '--', path).stdout.strip()
        if entries != f'100644 {blob} 0\t{path}':
            raise InheritanceError('Reviewed settings companion index changed: ' + path)
        target = repo / path
        if target.is_symlink() or not target.resolve().is_relative_to(repo):
            raise InheritanceError('Unsafe settings companion path: ' + path)
        text = target.read_text(encoding='utf-8')
        data = text.encode('utf-8')
        actual_blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if actual_blob != blob:
            raise InheritanceError('Reviewed settings companion content changed: ' + path)
        data = settings_companion(path, text).encode('utf-8')
        if hashlib.sha256(data).hexdigest() != digest:
            raise InheritanceError('Reviewed settings companion output changed: ' + path)
        outputs[path] = data
    for path in outputs:
        target = repo / path
        if target.is_symlink() or not target.resolve().is_relative_to(repo):
            raise InheritanceError('Unsafe settings output path: ' + path)
    return outputs


def git(repo, *args, check=True):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                            text=True)
    if check and result.returncode:
        raise InheritanceError('Git operation failed: ' + args[0])
    return result


def reconcile_reviewed_merge(repo, base, upstream):
    expected = REVIEWED_RECONCILIATIONS.get(upstream)
    actual = {}
    for entry in git(repo, 'ls-files', '--unmerged', '-z').stdout.split('\0'):
        if not entry:
            continue
        metadata, path = entry.split('\t', 1)
        mode, blob, stage = metadata.split()
        if mode != '100644':
            raise InheritanceError('Unreviewed conflict mode: ' + path)
        actual.setdefault(path, {})[int(stage)] = blob
    if not expected or actual != {
            path: dict(enumerate(blobs, 1)) for path, blobs in expected.items()}:
        raise InheritanceError('Merge conflicts differ from the exact reviewed reconciliation')
    if upstream == SETTINGS_UPSTREAM:
        outputs = settings_outputs(repo)
        for path, data in outputs.items():
            (Path(repo) / path).write_bytes(data)
        git(repo, 'add', '--', *outputs)
        git(repo, 'commit', '--no-edit')
        return
    # Validate the whole conflict set before changing any file. Prepared TailD
    # blobs already integrate typed routes and preserve the fork's shell/hooks.
    git(repo, 'restore', '--source=' + base, '--staged', '--worktree', '--', *expected)
    git(repo, 'commit', '--no-edit')


def core_pin(text):
    required = re.findall(r'^\s*(?:require\s+)?tailscale\.com\s+(v\S+)\s*$', text, re.M)
    replaced = re.findall(r'^replace tailscale\.com => github\.com/Darkaxt/tailscale (v\S+)\s*$',
                          text, re.M)
    if len(required) != 1 or required != replaced:
        raise InheritanceError('Expected matching TailDNS shared-core require/replace pins')
    return required[0]


def prepare(repo, upstream_ref='refs/remotes/taildns/main'):
    repo = Path(repo).resolve()
    if git(repo, 'status', '--porcelain').stdout:
        raise InheritanceError('Refusing to modify a dirty checkout')
    base = git(repo, 'rev-parse', 'HEAD').stdout.strip()
    upstream = git(repo, 'rev-parse', '--verify', upstream_ref + '^{commit}').stdout.strip()
    upstream_pin = core_pin(git(repo, 'show', upstream + ':go.mod').stdout)
    base_workflows = set(git(repo, 'ls-tree', '-r', '--name-only', base,
                             '.github/workflows').stdout.splitlines())
    upstream_workflows = set(git(repo, 'ls-tree', '-r', '--name-only', upstream,
                                 '.github/workflows').stdout.splitlines())
    if upstream_workflows - base_workflows:
        raise InheritanceError('New inherited workflows require review and disabling before promotion')
    changed = git(repo, 'merge-base', '--is-ancestor', upstream, base,
                  check=False).returncode != 0
    if changed:
        merged = git(repo, '-c', 'merge.autoStash=false', 'merge', '--no-ff', '--no-edit',
                     upstream, check=False)
        if merged.returncode:
            reconcile_reviewed_merge(repo, base, upstream)
    candidate = git(repo, 'rev-parse', 'HEAD').stdout.strip()
    if core_pin(git(repo, 'show', candidate + ':go.mod').stdout) != upstream_pin:
        raise InheritanceError('Candidate shared-core pin differs from captured TailDNS upstream')
    git(repo, 'merge-base', '--is-ancestor', base, candidate)
    git(repo, 'merge-base', '--is-ancestor', upstream, candidate)
    changed_paths = git(repo, 'diff', '--name-only', base, candidate).stdout.splitlines()
    source_changed = any(not (path.startswith(('docs/', '.github/', 'scripts/taild/'))
                              or path == 'README.md') for path in changed_paths)
    return dict(changed=changed, source_changed=source_changed,
                base=base, upstream=upstream, candidate=candidate)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='.')
    parser.add_argument('--upstream-ref', default='refs/remotes/taildns/main')
    parser.add_argument('--output', help='GitHub Actions output file')
    args = parser.parse_args()
    try:
        result = prepare(args.repo, args.upstream_ref)
    except InheritanceError as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(result))
    if args.output:
        with open(args.output, 'a', encoding='utf-8') as output:
            for key, value in result.items():
                output.write(f'{key}={str(value).lower()}\n')


if __name__ == '__main__':
    main()
