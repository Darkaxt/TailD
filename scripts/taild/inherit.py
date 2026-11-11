"""Prepare a checked TailDNS merge. This command never fetches or pushes."""

import argparse
import json
from pathlib import Path
import re
import subprocess


class InheritanceError(RuntimeError):
    pass


# Reviewed typed-navigation reconciliation. Each tuple is the exact common,
# prepared TailD, and upstream blob. Unknown revisions/conflicts still fail.
REVIEWED_RECONCILIATIONS = {
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
