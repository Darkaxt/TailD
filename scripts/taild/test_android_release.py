"""Reject misleading Android payload identity before signing or delivery."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

import android_release as release


class AndroidPayloadContract(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="taild-android-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.apk = Path(self.temporary.name) / "fixture.apk"
        self.metadata = {"source_revision": "a" * 40, "core_revision": "b" * 40, "version_name": "1.103.312+1"}

    def build(self, wrong_abi=False, wrong_core=False, duplicate=False):
        with zipfile.ZipFile(self.apk, "w") as archive:
            for abi, (elf_class, machine) in release.ABIS.items():
                data = bytearray(64)
                data[:4] = b"\x7fELF"
                data[4:6] = bytes((elf_class, 1))
                struct.pack_into("<H", data, 18, 3 if wrong_abi else machine)
                data += ("a" * 40 + ("c" if wrong_core else "b") * 40 + "1.103.312").encode()
                archive.writestr(f"lib/{abi}/libgojni.so", data)
            archive.writestr(release.METADATA, json.dumps(self.metadata))
            archive.writestr("assets/taild-notices.txt", "TailD inherited notices")
            archive.writestr("assets/taild-license.txt", "fixture license")
            if duplicate:
                archive.writestr(release.METADATA, json.dumps(self.metadata))

    def test_all_architectures_and_both_embedded_source_identities_are_required(self):
        self.build()
        inventory = release.members(self.apk, self.metadata)
        self.assertEqual(len(inventory), 7)
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
