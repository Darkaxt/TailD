"""Reject misleading Android payload identity before signing or delivery."""
import json
import ast
from pathlib import Path
import re
import struct
import tempfile
import textwrap
import unittest
import zipfile

import android_release as release


class AndroidPayloadContract(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="taild-android-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.apk = Path(self.temporary.name) / "fixture.apk"
        self.metadata = {"source_revision": "a" * 40, "core_revision": "b" * 40,
                         "upstream_android_version": "1.103.312", "taild_sequence": 36,
                         "version_name": "1.103.312.36", "tag": "v1.103.312.36"}
        self.map_bytes = (release.ROOT / "android/src/main/assets/taild-world-map.json").read_bytes()
        self.metadata["country_map_sha256"] = release.digest(self.map_bytes)

    def test_dotted_version_preserves_the_three_part_upstream_base(self):
        self.assertEqual(release.version_name("1.103.312", "36"), "1.103.312.36")
        for base, sequence in [("1.103", "36"), ("1.103.312.36", "37"),
                               ("1.103.312", "0"), ("1.103.312", "01"),
                               ("1.103.312", "36+1")]:
            with self.subTest(base=base, sequence=sequence), self.assertRaises(AssertionError):
                release.version_name(base, sequence)

    def test_version_tag_and_sequence_must_agree_before_payload_verification(self):
        self.build()
        for replacement in [{"version_name": "1.103.312+36"},
                            {"tag": "v1.103.312+36"},
                            {"taild_sequence": 35},
                            {"upstream_android_version": "1.103.312.36"}]:
            with self.subTest(replacement=replacement), self.assertRaises(AssertionError):
                release.members(self.apk, self.metadata | replacement)

    def test_publication_guard_preserves_legacy_and_dotted_sequence_history(self):
        workflow = (release.ROOT / ".github/workflows/taild-android-release.yml").read_text()
        functions = []
        for block in re.findall(r"python3 - <<'PY'\n(.*?)\n          PY", workflow, re.S):
            functions.extend(node for node in ast.parse(textwrap.dedent(block)).body
                             if isinstance(node, ast.FunctionDef) and node.name == "android_sequence")
        self.assertEqual(len(functions), 1)
        namespace = {"re": re}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "publication guard", "exec"), namespace)
        sequence = namespace["android_sequence"]
        self.assertEqual(sequence("v1.103.312+35"), 35)
        self.assertEqual(sequence("v1.103.312.36"), 36)
        self.assertEqual(sequence("v1.104.0.37"), 37)
        for tag in ["windows-v1.105.0+28", "v1.103.312.0", "v1.103.312.036", "v1.103.312.36.extra"]:
            with self.subTest(tag=tag), self.assertRaises(AssertionError):
                sequence(tag)

    def test_signed_metadata_binds_offline_map_bytes(self):
        self.build(wrong_map=True)
        with self.assertRaises(AssertionError):
            release.members(self.apk, self.metadata)

    def build(self, wrong_abi=False, wrong_core=False, duplicate=False, wrong_map=False):
        with zipfile.ZipFile(self.apk, "w") as archive:
            for abi, (elf_class, machine) in release.ABIS.items():
                data = bytearray(64)
                data[:4] = b"\x7fELF"
                data[4:6] = bytes((elf_class, 1))
                struct.pack_into("<H", data, 18, 3 if wrong_abi else machine)
                data += ("a" * 40 + ("c" if wrong_core else "b") * 40 + "1.103.312").encode()
                archive.writestr(f"lib/{abi}/libgojni.so", data)
            archive.writestr(release.METADATA, json.dumps(self.metadata))
            archive.writestr("assets/taild-notices.txt", "TailD inherited notices; Natural Earth")
            archive.writestr("assets/taild-license.txt", "fixture license")
            archive.writestr("assets/taild-map-license.txt", "GNU GENERAL PUBLIC LICENSE")
            archive.writestr("assets/taild-world-map.json", b"{}" if wrong_map else self.map_bytes)
            if duplicate:
                archive.writestr(release.METADATA, json.dumps(self.metadata))

    def test_all_architectures_and_both_embedded_source_identities_are_required(self):
        self.build()
        inventory = release.members(self.apk, self.metadata)
        self.assertEqual(len(inventory), 9)
        self.build(wrong_abi=True)
        with self.assertRaises(AssertionError):
            release.members(self.apk, self.metadata)
        self.build(wrong_core=True)
        with self.assertRaises(AssertionError):
            release.members(self.apk, self.metadata)

    def test_duplicate_metadata_cannot_shadow_the_signed_identity(self):
        self.build(duplicate=True)
        with self.assertRaises(AssertionError):
            release.members(self.apk, self.metadata)


if __name__ == "__main__":
    unittest.main()
