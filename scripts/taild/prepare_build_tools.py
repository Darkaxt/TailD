"""Fetch exact inherited CI tools through GitHub's release-asset API.

The public browser-download edge can return 504 while the asset API is healthy.
This runs only in the read-only Linux verification job; it has no signing key.
"""
import hashlib
import json
import os
import re
import subprocess
import tarfile
import zipfile
from pathlib import Path


def release_asset(repository, tag, name, expected_sha256=None):
    metadata = json.loads(subprocess.check_output(
        ['gh', 'api', f'repos/{repository}/releases/tags/{tag}'], text=True))
    assert metadata['tag_name'] == tag and not metadata['draft']
    assets = [a for a in metadata['assets'] if a['name'] == name]
    assert len(assets) == 1, (repository, tag, name)
    asset = assets[0]
    digest = asset.get('digest', '')
    assert re.fullmatch(r'sha256:[0-9a-f]{64}', digest), 'Missing asset digest'
    if expected_sha256 is not None:
        assert digest == 'sha256:' + expected_sha256, 'Source checksum mismatch'
    return asset, digest.removeprefix('sha256:')


def download(repository, asset, digest, destination):
    assert not destination.exists()
    with destination.open('xb') as output:
        subprocess.run(['gh', 'api', '-H', 'Accept: application/octet-stream',
                        f'repos/{repository}/releases/assets/{asset["id"]}'],
                       stdout=output, check=True)
    assert destination.stat().st_size == asset['size'], 'Asset size mismatch'
    with destination.open('rb') as data:
        assert hashlib.file_digest(data, 'sha256').hexdigest() == digest, 'Asset checksum mismatch'


def main():
    assert os.environ.get('RUNNER_OS') == 'Linux'
    root = Path(__file__).resolve().parents[2]
    scratch = Path(os.environ['RUNNER_TEMP']) / 'taild-inherited-build-tools'
    scratch.mkdir(exist_ok=False)
    revision = (root / 'go.toolchain.rev').read_text().strip()
    assert re.fullmatch('[0-9a-f]{40}', revision)
    properties = dict(line.split('=', 1) for line in
                      (root / 'android/gradle/wrapper/gradle-wrapper.properties').read_text().splitlines()
                      if '=' in line and not line.startswith('#'))
    match = re.search(r'/gradle-([0-9.]+)-bin.zip$', properties['distributionUrl'])
    assert match
    version = match[1]
    asset, digest = release_asset('tailscale/go', 'build-' + revision, 'linux-amd64.tar.gz')
    archive = scratch / asset['name']
    download('tailscale/go', asset, digest, archive)
    toolchain = scratch / 'toolchain'
    toolchain.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(toolchain, filter='data')
    go = toolchain / 'go'
    assert (go / 'bin/go').is_file() and (go / 'VERSION').is_file()
    name = f'gradle-{version}-bin.zip'
    asset, digest = release_asset('gradle/gradle-distributions', 'v' + version, name,
                                  properties['distributionSha256Sum'])
    archive = scratch / name
    download('gradle/gradle-distributions', asset, digest, archive)
    with zipfile.ZipFile(archive) as source:
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in source.namelist())
        source.extractall(scratch)
    gradle = scratch / ('gradle-' + version) / 'bin/gradle'
    assert gradle.is_file()
    gradle.chmod(0o755)
    with Path(os.environ['GITHUB_ENV']).open('a') as output:
        output.write(f'TOOLCHAINDIR={go}\nTAILD_GRADLE_BIN={gradle}\n')
    print(json.dumps({'go_revision': revision, 'gradle_version': version,
                      'source_pinned_gradle_checksum': properties['distributionSha256Sum'],
                      'download_route': 'GitHub release asset API', 'verified': True}))


if __name__ == '__main__':
    main()
