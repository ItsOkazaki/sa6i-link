"""Checks on the Sa6i Clean delivery package.

These are static checks: the package is a set of text scripts plus a prebuilt
bundle, and the point is to catch a package whose words and hashes disagree
with the bundle it carries, or whose scripts would fail on Windows 7.
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

HEADER_HASH = "653f05e211811d173cd943c6fc44aecb6c9318a3091010abafcb4abca87e5a0a"
PATCH_NAME = "Install-Sa6i-Clean-Patch.ps1"
RETARGET_NAME = "Retarget-Sa6i-Clean-Digests.ps1"


def source(name: str) -> str:
    return (HERE / name).read_text(encoding="utf-8")


def ps1_code(name: str) -> str:
    """A patch script with its comment lines removed."""
    return "\n".join(
        line for line in source(name).splitlines() if not line.lstrip().startswith("#")
    )


class DeliveryFilesTest(unittest.TestCase):
    def test_payload_files_exist(self):
        for source_name, _ in build_delivery.PAYLOAD:
            self.assertTrue((HERE / source_name).is_file(), source_name)

    def test_readme_states_the_expected_bundle_hash(self):
        readme = source("README.txt")
        self.assertIn(build_delivery.EXPECTED_ASAR_SHA, readme)

    def test_readme_states_the_debranded_header_hash(self):
        self.assertIn(HEADER_HASH, source("README.txt"))

    def test_scripts_expect_the_debranded_header_hash(self):
        self.assertIn("$expectedNew = '" + HEADER_HASH + "'", source(PATCH_NAME))

    def test_patch_reads_the_installed_hash_instead_of_pinning_it(self):
        # The old script refused any build but one exact version; the hash now
        # comes from the bundle that is actually installed.
        script = source(PATCH_NAME)
        self.assertIn("$oldHash = Get-HeaderHash $oldAsar", script)
        self.assertNotIn("$expectedOld", script)

    def test_readme_says_where_app_asar_must_and_must_not_go(self):
        readme = source("README.txt")
        self.assertIn("NOT inside resources", readme)
        self.assertIn("app.asar", readme)
        self.assertNotIn("three files into", readme)

    def test_readme_covers_both_steps(self):
        readme = source("README.txt")
        self.assertIn("Apply Sa6i Clean Patch.cmd", readme)
        self.assertIn("Retarget Sa6i Clean.cmd", readme)

    def test_patch_names_the_previous_bundle_when_the_copy_was_missed(self):
        script = source(PATCH_NAME)
        self.assertIn("8e6ee85e794723de784eb1adc1baedf28a612f968e7b88970297f91053e37fb9", script)
        self.assertIn("previous debranded bundle", script)
        self.assertIn("1,420,960 bytes", script)

    def test_rerunning_keeps_the_oldest_backup(self):
        self.assertIn("Test-Path -LiteralPath ($exe + '.bak')", source(PATCH_NAME))
        self.assertIn("Test-Path -LiteralPath ($Desktop + '.bak')", source(RETARGET_NAME))

    def test_retarget_finds_the_launcher_instead_of_assuming_its_name(self):
        code = ps1_code(RETARGET_NAME)
        self.assertIn("Looking for the Sa6i Link executable", code)
        self.assertNotIn("Join-Path $here 'sa6i-link.exe'", code)
        self.assertNotIn("Join-Path $here \"sa6i-link.exe\"", code)

    def test_retarget_scans_files_small_enough_to_be_the_launcher(self):
        # Sa6i Link is a Tauri build: its exe is around ten megabytes, so any
        # size floor must stay well below that. The cleaner is the big one.
        code = ps1_code(RETARGET_NAME)
        self.assertIn("($_.Length -gt 1048576)", code)
        self.assertNotIn("20971520", code)

    def test_retarget_writes_the_digests_without_array_copy(self):
        # Windows PowerShell 2.0 hands Object[] back from a function that
        # returns byte[], and Array::Copy then refuses the cast - which is
        # exactly how this step failed on the user's machine.
        code = ps1_code(RETARGET_NAME)
        self.assertNotIn("[Array]::Copy", code)
        self.assertIn("[byte[]] $newExe = Get-HashBytes", code)
        self.assertIn("[byte[]] $newAsar = Get-HashBytes", code)

    def test_retarget_verifies_without_holding_the_file_twice(self):
        code = ps1_code(RETARGET_NAME)
        self.assertIn("Count-InFile $Desktop", code)

    def test_patch_avoids_net_four_only_apis(self):
        # Windows 7 ships Windows PowerShell 2.0 on .NET 3.5. Dispose() on a
        # hash object and System.IO.Compression both fail there, which is what
        # an earlier package hit on the user's machine.
        for name in (PATCH_NAME, RETARGET_NAME):
            code = ps1_code(name)
            self.assertNotIn(".Dispose()", code, name)
            self.assertNotIn("System.IO.Compression", code, name)
            self.assertNotIn("Is64BitProcess", code, name)
            self.assertIn("[void]$sha.Clear()", code, name)

    def test_packing_uses_the_zip_support_built_into_windows(self):
        code = ps1_code(RETARGET_NAME)
        self.assertIn("CopyHere", code)
        self.assertIn("Shell.Application", code)

    def test_packing_happens_after_the_digests_are_retargeted(self):
        # An archive built before the retarget would ship an exe that refuses
        # the bundle it contains.
        code = ps1_code(RETARGET_NAME)
        self.assertLess(code.index("ConvertFrom-Hex $chosen"), code.index("New-CandidateZip $here"))

    def test_scripts_park_backups_out_of_the_archive(self):
        code = ps1_code(RETARGET_NAME)
        self.assertIn("'*.bak'", code)
        self.assertIn("'*-log.txt'", code)

    def test_patch_renames_the_executable_description_but_not_by_truncating(self):
        code = ps1_code(PATCH_NAME)
        self.assertIn("Unicode.GetBytes('Cleanly')", code)
        # Only values that end there are rewritten; longer ones are reported.
        self.assertIn("Left ' + $kept + ' field(s) alone", code)

    def test_retarget_knows_the_builds_it_may_be_pointing_at(self):
        code = ps1_code(RETARGET_NAME)
        self.assertIn("2c9bdd29209ebc58103753a2a66d8b9c840d94054eea368239566b5d42408d74", code)
        self.assertIn("4cbe981c5a473d61a7b679e61db49b4c5a0a052ba5783ce903054b46562a10ba", code)

    def test_launchers_keep_the_window_open(self):
        for name in ("Apply Sa6i Clean Patch.cmd", "Retarget Sa6i Clean.cmd"):
            launcher = source(name)
            self.assertIn("pause", launcher, name)
            self.assertIn("-log.txt", launcher, name)


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

    def test_packs_the_two_folders_with_windows_line_endings(self):
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
                self.assertEqual(archive.read(build_delivery.ASAR_ENTRY), b"bundle")
                for _, entry in build_delivery.PAYLOAD:
                    data = archive.read(entry)
                    self.assertNotIn(b"\n", data.replace(b"\r\n", b""), entry)
                    self.assertIn(b"\r\n", data, entry)
            expected = sorted([entry for _, entry in build_delivery.PAYLOAD]
                              + [build_delivery.ASAR_ENTRY])
            self.assertEqual(sorted(names), expected)
            self.assertTrue(any(name.startswith(build_delivery.CLEAN_FOLDER + "/")
                                for name in names))
            self.assertTrue(any(name.startswith(build_delivery.CANDIDATE_FOLDER + "/")
                                for name in names))


if __name__ == "__main__":
    unittest.main()
