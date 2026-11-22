"""Checks on the Sa6i Clean delivery package.

These are static checks: the delivery is three text files plus a prebuilt
bundle, and the point is to catch a package whose words and hashes disagree
with the bundle it carries.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_delivery  # noqa: E402

HEADER_HASH = "8e6ee85e794723de784eb1adc1baedf28a612f968e7b88970297f91053e37fb9"


class DeliveryFilesTest(unittest.TestCase):
    def test_payload_files_exist(self):
        for name in build_delivery.PAYLOAD:
            self.assertTrue((HERE / name).is_file(), name)

    def test_readme_states_the_expected_bundle_hash(self):
        readme = (HERE / "README.txt").read_text(encoding="utf-8")
        self.assertIn(build_delivery.EXPECTED_ASAR_SHA, readme)

    def test_readme_states_the_debranded_header_hash(self):
        readme = (HERE / "README.txt").read_text(encoding="utf-8")
        self.assertIn(HEADER_HASH, readme)

    def test_script_expects_the_debranded_header_hash(self):
        script = (HERE / "Install-Sa6i-Clean-Patch.ps1").read_text(encoding="utf-8")
        self.assertIn("$expectedNew = '" + HEADER_HASH + "'", script)

    def test_script_reads_the_installed_hash_instead_of_pinning_it(self):
        # The old script refused any build but one exact version; the hash now
        # comes from the bundle that is actually installed.
        script = (HERE / "Install-Sa6i-Clean-Patch.ps1").read_text(encoding="utf-8")
        self.assertIn("$oldHash = Get-HeaderHash $oldAsar", script)
        self.assertNotIn("$expectedOld", script)

    def test_readme_tells_the_user_to_copy_all_four_files(self):
        # The script reads app.asar from its own folder, so a package
        # described as "three files" cannot work.
        readme = (HERE / "README.txt").read_text(encoding="utf-8")
        self.assertIn("all four files", readme)
        self.assertIn("app.asar", readme)
        self.assertNotIn("three files", readme)

    def test_script_needs_the_bundle_beside_it(self):
        script = (HERE / "Install-Sa6i-Clean-Patch.ps1").read_text(encoding="utf-8")
        self.assertIn("$newAsar = Join-Path $here 'app.asar'", script)
        self.assertIn("app.asar is not next to this script.", script)

    def test_launcher_keeps_the_window_open(self):
        launcher = (HERE / "Apply Sa6i Clean Patch.cmd").read_text(encoding="utf-8")
        self.assertIn("pause", launcher)
        self.assertIn("patch-log.txt", launcher)


class BuildDeliveryTest(unittest.TestCase):
    def test_rejects_a_bundle_that_is_not_the_debranded_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            asar = pathlib.Path(tmp) / "app.asar"
            asar.write_bytes(b"\x04\x00\x00\x00" + b"\x00" * 64)
            out = pathlib.Path(tmp) / "bundle.zip"
            with self.assertRaises(SystemExit):
                build_delivery.build(asar, out)
            self.assertFalse(out.exists())

    def test_rejects_a_missing_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "bundle.zip"
            with self.assertRaises(SystemExit):
                build_delivery.build(pathlib.Path(tmp) / "absent.asar", out)
            self.assertFalse(out.exists())

    def test_packs_four_named_files_when_the_bundle_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            asar = pathlib.Path(tmp) / "app.asar"
            asar.write_bytes(b"bundle")
            out = pathlib.Path(tmp) / "bundle.zip"
            original = build_delivery.EXPECTED_ASAR_SHA
            build_delivery.EXPECTED_ASAR_SHA = build_delivery.sha256_of(asar)
            try:
                build_delivery.build(asar, out)
            finally:
                build_delivery.EXPECTED_ASAR_SHA = original
            with zipfile.ZipFile(out) as archive:
                names = archive.namelist()
                self.assertEqual(archive.read("app.asar"), b"bundle")
                for name in build_delivery.PAYLOAD:
                    data = archive.read(name)
                    self.assertNotIn(b"\n", data.replace(b"\r\n", b""), name)
                    self.assertIn(b"\r\n", data, name)
            self.assertEqual(
                sorted(names),
                sorted(list(build_delivery.PAYLOAD) + ["app.asar"]),
            )


if __name__ == "__main__":
    unittest.main()
