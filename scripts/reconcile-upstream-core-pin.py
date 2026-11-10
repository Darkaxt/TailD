"""Resolve owned core pins and an exact reviewed interface conflict; fail closed."""
import argparse
from pathlib import Path
import re
import subprocess


INTERFACE_PATH = 'libtailscale/interfaces.go'
INTERFACE_BLOBS = {
    '1': '8adbcc188a0b80384e7b6b9b84d9e19f4aee5588',
    '2': 'bf25cad6d862f80dcea530075ded05ce9b6806f5',
    '3': 'ac702a03c6aea91edbca70cc390fa2e1848e11b6',
}


def validate_paths(paths):
    if paths not in ({'go.mod', 'go.sum'}, {'go.mod', 'go.sum', INTERFACE_PATH}):
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
    for name in sorted(stages):
        path = Path(name)
        if path.is_symlink():
            raise ValueError('Conflict path is a symlink')
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
    for name, text in resolved.items():
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
