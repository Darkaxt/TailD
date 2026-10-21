"""Exact-source Android package metadata and independent APK verification.

Build/verification only: this file never receives a signing key or publishes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import zipfile

if not __debug__:
    raise RuntimeError("Android delivery verification must run without Python optimization")

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "io.github.darkaxt.taildns"
SIGNER = "dcd0ede91eb7e0ed88a72b5289f84f8d4a61ccc22707f36378e15540b99d32e1"
ABIS = {"arm64-v8a": (2, 183), "armeabi-v7a": (1, 40), "x86": (1, 3), "x86_64": (2, 62)}
METADATA = "assets/taild-build.json"


def command(*args: str, env: dict | None = None) -> str:
    return subprocess.check_output(args, cwd=ROOT, env=env, text=True, encoding="utf-8").strip()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def version_name(base: str, sequence: str | int) -> str:
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", base)
    assert re.fullmatch(r"[1-9][0-9]*", str(sequence))
    return f"{base}.{sequence}"


def prepare(_: argparse.Namespace) -> None:
    source = command("git", "rev-parse", "HEAD")
    assert re.fullmatch(r"[0-9a-f]{40}", source)
    # Generated build outputs below are ignored. Tracked source must be exact.
    assert not command("git", "status", "--porcelain", "--untracked-files=normal"), "Build exact clean committed source"
    sequence = (ROOT / "TAILD_ANDROID_SEQUENCE.txt").read_text().strip()
    base = (ROOT / "TAILSCALE_BASE_VERSION.txt").read_text().strip()
    assert re.fullmatch(r"[1-9][0-9]*", sequence)
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", base)
    env = os.environ | {"TAILDNS_RELEASE_SEQUENCE": sequence}
    version = command("bash", "scripts/fork-mkversion.sh", env=env)
    (ROOT / "tailscale.version").write_text(version + "\n", encoding="utf-8")
    values = dict(line.split("=", 1) for line in version.splitlines() if "=" in line)
    values = {key: value.strip('"') for key, value in values.items()}
    assert values["VERSION_SHORT"] == base
    assert values["TAILDNS_VERSION_NAME"] == version_name(base, sequence)
    assert values["VERSION_EXTRA_HASH"] == source
    module = json.loads(command("bash", "tool/go", "list", "-m", "-json", "tailscale.com"))
    replace = module["Replace"]
    assert replace["Path"] == "github.com/Darkaxt/tailscale"
    assert replace["Version"] == module["Version"]
    core = values["VERSION_GIT_HASH"]
    assert re.fullmatch(r"[0-9a-f]{40}", core)
    assert replace["Version"].endswith("-" + core[:12])
    code = int(command("git", "show", "-s", "--format=%ct", source)) // 60 * 10
    assert 0 < code < 2147483640
    metadata = {
        "product": "TailD Android", "schema": 1, "history_schema": 1,
        "source_revision": source, "core_revision": core,
        "core_module": f"{replace['Path']} {replace['Version']}",
        "core_version": (Path(replace["Dir"]) / "VERSION.txt").read_text().strip(),
        "upstream_android_version": base, "taild_sequence": int(sequence),
        "version_name": version_name(base, sequence), "version_code": code,
        "tag": f"v{version_name(base, sequence)}", "package": PACKAGE, "signer_sha256": SIGNER,
        "go_toolchain_revision": (ROOT / "go.toolchain.rev").read_text().strip(),
        "go_version": command("bash", "tool/go", "version"),
        "country_map_sha256": digest((ROOT / "android/src/main/assets/taild-world-map.json").read_bytes()),
    }
    write_json(ROOT / "android/src/main/assets/taild-build.json", metadata)
    print(json.dumps(metadata, sort_keys=True))


def members(apk: Path, metadata: dict) -> dict:
    name = version_name(metadata["upstream_android_version"], metadata["taild_sequence"])
    assert metadata["version_name"] == name and metadata["tag"] == f"v{name}"
    assert apk.stat().st_size < 200 * 1024 * 1024
    result = {}
    abis = set()
    with zipfile.ZipFile(apk) as archive:
        infos = archive.infolist()
        assert len(infos) < 20_000 and sum(info.file_size for info in infos) < 500 * 1024 * 1024
        for info in infos:
            name = info.filename
            assert name not in result and not name.startswith("/") and ".." not in name.split("/") and "\\" not in name
            assert info.file_size < 128 * 1024 * 1024
            data = archive.read(info)
            result[name] = {"sha256": digest(data), "size": len(data)}
            if name.startswith("lib/") and name.endswith("/libgojni.so"):
                abi = name.split("/")[1]
                assert abi in ABIS and abi not in abis
                abis.add(abi)
                assert data[:4] == b"\x7fELF" and data[5] == 1
                assert (data[4], struct.unpack_from("<H", data, 18)[0]) == ABIS[abi]
                for identity in (metadata["source_revision"], metadata["core_revision"], metadata["upstream_android_version"]):
                    assert identity.encode() in data, f"Native provenance missing: {abi}"
        assert abis == ABIS.keys()
        assert json.loads(archive.read(METADATA)) == metadata
        assert b"TailD" in archive.read("assets/taild-notices.txt")
        assert "assets/taild-license.txt" in result
        assert result["assets/taild-world-map.json"]["sha256"] == metadata["country_map_sha256"]
        assert b"Natural Earth" in archive.read("assets/taild-notices.txt")
        assert b"GNU GENERAL PUBLIC LICENSE" in archive.read("assets/taild-map-license.txt")
        notices = archive.read("assets/taild-notices.txt")
        assert b"ShizuWall" in notices and b"Shizuku" in notices
        for name in ("taild-shizuwall-license.txt", "taild-shizuku-license.txt"):
            assert digest(archive.read("assets/" + name)) == digest((ROOT / "android/src/main/assets" / name).read_bytes())
    return result


def package(args: argparse.Namespace) -> None:
    output = args.directory.resolve()
    assert not output.exists(), "Use a new exact task-owned output directory"
    output.mkdir(parents=True)
    metadata = json.loads((ROOT / "android/src/main/assets/taild-build.json").read_text())
    assert metadata["source_revision"] == command("git", "rev-parse", "HEAD")
    source = ROOT / "android/build/outputs/apk/release/android-release-unsigned.apk"
    shutil.copyfile(source, output / "taild-android-unsigned.apk")
    write_json(output / "build.json", metadata)
    write_json(output / "payloads.json", members(source, metadata))
    shutil.copyfile(ROOT / "docs/taild/ANDROID-RELEASE-NOTES.md", output / "release-notes.md")
    print(json.dumps({"source": metadata["source_revision"], "unsigned_apk_sha256": digest(source.read_bytes())}))


def verify(args: argparse.Namespace) -> None:
    directory = args.directory.resolve()
    metadata = json.loads((directory / "build.json").read_text())
    assert metadata["package"] == PACKAGE and metadata["signer_sha256"] == SIGNER
    assert metadata["tag"] == f"v{version_name(metadata['upstream_android_version'], metadata['taild_sequence'])}"
    assert metadata["version_name"] == metadata["tag"][1:]
    assert metadata["schema"] == metadata["history_schema"] == 1
    for field in ("source_revision", "core_revision", "go_toolchain_revision"):
        assert re.fullmatch(r"[0-9a-f]{40}", metadata[field])
    if args.source:
        assert metadata["source_revision"] == args.source
    if args.core:
        assert metadata["core_revision"] == args.core
    apk = directory / "taild-android.apk"
    sdk = args.tools.resolve()
    signer = sdk / ("apksigner.bat" if os.name == "nt" else "apksigner")
    aapt = sdk / ("aapt.exe" if os.name == "nt" else "aapt")
    signed = command(str(signer), "verify", "--verbose", "--print-certs", str(apk))
    assert signed.count("Signer #1 certificate SHA-256 digest:") == 1
    assert f"Signer #1 certificate SHA-256 digest: {SIGNER}" in signed
    assert "Number of signers: 1" in signed
    badging = command(str(aapt), "dump", "badging", str(apk))
    assert f"package: name='{PACKAGE}'" in badging
    assert f"versionCode='{metadata['version_code']}'" in badging
    assert f"versionName='{metadata['version_name']}'" in badging
    assert "application-label:'TailD'" in badging
    manifest = command(str(aapt), "dump", "xmltree", str(apk), "AndroidManifest.xml")
    assert not re.search(r"debuggable.*0xffffffff", manifest)
    assert "android.intent.action.MAIN" in manifest and "android.net.VpnService" in manifest
    assert "IPNReceiver" in manifest and "taildns" in manifest
    inventory = members(apk, metadata)
    expected = json.loads((directory / "payloads.json").read_text())
    signatures = re.compile(r"META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC))$", re.I)
    assert {name: value for name,value in inventory.items() if not signatures.fullmatch(name)} == {
        name:value for name,value in expected.items() if not signatures.fullmatch(name)
    }, "Signed APK differs from checked unsigned payload"
    sums = dict((name, checksum) for checksum,name in (line.split(maxsplit=1) for line in (directory / "SHA256SUMS").read_text().splitlines()))
    allowed = {"taild-android.apk", "taild-android.apk.idsig", "build.json", "payloads.json", "signature.txt", "package.txt", "provenance.txt", "release-notes.md"}
    assert {"taild-android.apk", "build.json", "payloads.json", "provenance.txt"} <= sums.keys()
    assert sums.keys() <= allowed
    for name, checksum in sums.items():
        assert re.fullmatch(r"[0-9a-f]{64}", checksum)
        assert digest((directory / name).read_bytes()) == sums[name]
    report = {"verified": True, "tag": metadata["tag"], "source": metadata["source_revision"],
              "core": metadata["core_revision"], "package": PACKAGE, "version_code": metadata["version_code"],
              "signer_sha256": SIGNER, "apk_sha256": digest(apk.read_bytes()), "payload_members": len(inventory), "abis": sorted(ABIS)}
    if args.report:
        write_json(args.report, report)
    print(json.dumps(report, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("prepare").set_defaults(run=prepare)
    packing = sub.add_parser("package")
    packing.add_argument("--directory", type=Path, required=True)
    packing.set_defaults(run=package)
    checking = sub.add_parser("verify")
    checking.add_argument("--directory", type=Path, required=True)
    checking.add_argument("--tools", type=Path, required=True)
    checking.add_argument("--source")
    checking.add_argument("--core")
    checking.add_argument("--report", type=Path)
    checking.set_defaults(run=verify)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
