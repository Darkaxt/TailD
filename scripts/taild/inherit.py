"""Prepare a checked TailDNS merge. This command never fetches or pushes."""

import argparse
import json
from pathlib import Path
import re
import subprocess


class InheritanceError(RuntimeError):
    pass


def git(repo, *args, check=True):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                            text=True)
    if check and result.returncode:
        raise InheritanceError('Git operation failed: ' + args[0])
    return result


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
        git(repo, '-c', 'merge.autoStash=false', 'merge', '--no-ff', '--no-edit', upstream)
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
