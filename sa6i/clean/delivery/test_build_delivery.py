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

    def test_retarget_renames_the_launcher_and_its_product_strings(self):
        code = ps1_code(RETARGET_NAME)
        # The launcher's own name is part of the branding the user asked for.
        self.assertIn("'NectarLink'", code)
        self.assertIn("'Sa6i Link.exe'", code)
        self.assertIn("[System.IO.File]::Move($launcherPath, $newPath)", code)

    def test_retarget_leaves_utf8_alone_in_the_launcher(self):
        # UTF-16 strings are file properties; the UTF-8 bytes in the same file
        # include configuration the application parses, where a NUL-truncated
        # value would stop it from starting.
        code = ps1_code(RETARGET_NAME)
        self.assertIn("Unicode.GetBytes('NectarLink')", code)
        self.assertNotIn("UTF8.GetBytes('NectarLink')", code)

    def test_retarget_fixes_launchers_that_name_the_old_executable(self):
        code = ps1_code(RETARGET_NAME)
        self.assertIn("$ctext.Replace($oldFile, $newFile)", code)
        self.assertIn("($_.Extension -eq '.cmd')", code)

    def test_branding_runs_before_the_folder_is_packed(self):
        code = ps1_code(RETARGET_NAME)
        self.assertLess(code.index("Branding the Sa6i Link executable"),
                        code.index("New-CandidateZip $here"))

    def test_retarget_checks_the_executable_can_be_written_first(self):
        # A running Sa6i Link locks its own exe; the user hit exactly that, in
        # the middle of the branding step, after the swap had been skipped.
        code = ps1_code(RETARGET_NAME)
        self.assertIn("Test-Writable $target.FullName", code)
        self.assertIn("FileShare]::None", code)
        self.assertLess(code.index("Test-Writable $target.FullName"),
                        code.index("if ($already)"))

    def test_retarget_closes_the_launcher_but_does_not_kill_it(self):
        code = ps1_code(RETARGET_NAME)
        self.assertIn("CloseMainWindow()", code)
        self.assertNotIn("Stop-Process -Force", code)
        self.assertIn("notification area", code)

    def test_retarget_avoids_cmdlets_whose_parameters_power_shell_2_lacks(self):
        # Rename-Item -LiteralPath exists only from PowerShell 3.0; using it
        # aborted the run one line after the strings had been renamed.
        code = ps1_code(RETARGET_NAME)
        for missing in ("Rename-Item", "Move-Item", "Remove-Item", "New-Item"):
            self.assertNotIn(missing, code, missing)
        self.assertIn("[System.IO.File]::Move($launcherPath, $newPath)", code)
        self.assertIn("[System.IO.Directory]::CreateDirectory($park)", code)
        self.assertIn("[System.IO.Directory]::Delete($park, $true)", code)

    def test_icon_replacement_walks_the_resource_section(self):
        code = ps1_code(RETARGET_NAME)
        self.assertIn("Get-PeInfo", code)
        self.assertIn("Get-ResourceLeaves $bytes $sections $root 3", code)
        self.assertIn("Get-ResourceLeaves $bytes $sections $root 14", code)
        # Both records of an image's length have to move with the data.
        self.assertIn("$bytes[$slot.SizeField + $b] = $length[$b]", code)
        self.assertIn("$bytes[$entry + 8 + $b] = $length[$b]", code)

    def test_resource_walk_refuses_implausible_counts(self):
        # The counts come from the file; a wrong offset read as a count would
        # otherwise mean millions of iterations, which is how this looked
        # frozen on the user's machine.
        code = ps1_code(RETARGET_NAME)
        self.assertIn("-gt 4096", code)
        self.assertIn("left alone, its slot reports", code)
        self.assertIn(": replacing ' + $best.Size", code)

    def test_nothing_is_written_until_it_reads_back(self):
        code = ps1_code(RETARGET_NAME)
        self.assertLess(code.index("$check = @(Get-ResourceLeaves $raw $info.Sections $root 14)"),
                        code.index("Say ('  writing '"))

    def test_missing_executable_points_at_the_backup(self):
        code = ps1_code(RETARGET_NAME)
        self.assertIn("rename the .bak back and run this again", code)

    def test_every_step_can_be_skipped_to_get_past_it(self):
        # The icon step is the riskiest one; being able to finish the pack
        # without it is what keeps a stuck step from blocking the deliverable.
        code = ps1_code(RETARGET_NAME)
        self.assertIn("[switch] $NoIcon", code)
        self.assertIn("if ($NoIcon) {", code)
        self.assertIn("[switch] $NoZip", code)

    def test_icon_step_says_where_it_is(self):
        code = ps1_code(RETARGET_NAME)
        for marker in ("found ' + $groupsBefore.Count", "resource section at byte", "replacement image(s) available"):
            self.assertIn(marker, code)

    def test_icon_replacement_puts_the_executable_back_when_it_fails(self):
        code = ps1_code(RETARGET_NAME)
        self.assertIn("[System.IO.File]::WriteAllBytes($exePath, $original)", code)

    def test_icon_step_runs_in_a_child_process_with_a_time_limit(self):
        # It hung on the user's machine and blocked the archive entirely.
        code = ps1_code(RETARGET_NAME)
        self.assertIn("-IconOnly", code)
        self.assertIn("Start-Process -FilePath $tempCmd", code)
        self.assertIn("$child.Kill()", code)
        self.assertIn("did not finish within 4 minutes", code)

    def test_icon_only_child_cannot_fall_through_into_the_main_flow(self):
        # Without this branch the child re-ran the whole script and started
        # another child, which is the recursion the user's console showed.
        code = ps1_code(RETARGET_NAME)
        self.assertIn("if ($IconOnly) {", code)
        self.assertIn("Invoke-IconReplacement $Desktop", code)
        self.assertLess(code.index("if ($IconOnly) {"),
                        code.index("Cleaner executable SHA-256"))
        # belt and braces: the child is told not to pack even if it got that far
        self.assertIn("-IconOnly -NoZip -Desktop", code)

    def test_log_says_which_build_ran(self):
        # A download that lands as "... (1).ps1" leaves the old script in place;
        # the banner is how the log shows which one executed.
        self.assertIn("script build ' + $scriptBuild", source(RETARGET_NAME))

    def test_icon_file_is_delivered_beside_the_retarget_script(self):
        names = dict(build_delivery.PAYLOAD)
        self.assertIn("Sa6i-Link-Icon.ico", names)
        self.assertTrue(names["Sa6i-Link-Icon.ico"].startswith(build_delivery.CANDIDATE_FOLDER))

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

    def test_shortcut_script_uses_only_what_windows_has(self):
        code = source("Make-Sa6i-Link-Shortcut.ps1")
        self.assertIn("New-Object -ComObject WScript.Shell", code)
        self.assertIn("$shortcut.IconLocation", code)
        # The launcher, not the batch file, is what the shortcut starts: a
        # windowed shortcut to a .cmd still flashes a console.
        self.assertIn("$shortcut.TargetPath = $wscript", code)
        self.assertIn("Sa6i Link (hidden).vbs", code)
        for banned in (".Dispose()", "Start-Job", "System.IO.Compression"):
            self.assertNotIn(banned, code, banned)

    def test_hidden_launcher_runs_the_batch_file_and_nothing_else(self):
        code = source("Make-Sa6i-Link-Shortcut.ps1")
        self.assertIn("shell.Run Chr(34) & \"' + $batch.FullName", code)
        self.assertIn("[System.IO.File]::WriteAllLines($launcher, $vbs)", code)

    def test_shortcut_script_keeps_the_batch_file_contents(self):
        # That is the only view of what the batch file does; without it the
        # batch file cannot be replaced by starting the executable directly.
        code = source("Make-Sa6i-Link-Shortcut.ps1")
        self.assertIn("[System.IO.File]::ReadAllLines($batch.FullName)", code)
        self.assertIn("shortcut-log.txt", code)
        self.assertIn("($_.Name -like 'Start*')", code)

    def test_shortcut_script_is_delivered_with_the_candidate_files(self):
        names = dict(build_delivery.PAYLOAD)
        for name in ("Make-Sa6i-Link-Shortcut.ps1", "Make Sa6i Link Shortcut.cmd"):
            self.assertIn(name, names)
            self.assertTrue(names[name].startswith(build_delivery.CANDIDATE_FOLDER))

    def test_profile_reset_points_at_a_new_profile_and_leaves_the_old_one(self):
        # Moving the folder fails while the application runs - it holds its own
        # profile open - so the path is changed instead.
        code = source("Reset-Sa6i-Link-Profile.ps1")
        self.assertIn("$lines[$index] = $replacement", code)
        self.assertNotIn("[System.IO.Directory]::Move", code)
        self.assertNotIn("Remove-Item", code)
        self.assertIn("The old profile is untouched", code)
        self.assertIn("($batch.FullName + '.bak')", code)

    def test_profile_reset_reads_the_location_from_the_batch_file(self):
        code = source("Reset-Sa6i-Link-Profile.ps1")
        self.assertIn("SA6I_DATA=(.*)", code)
        self.assertIn("ReadAllLines($batch.FullName)", code)

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
                for source_name, entry in build_delivery.PAYLOAD:
                    data = archive.read(entry)
                    if source_name.endswith(build_delivery.TEXT_SUFFIXES):
                        self.assertNotIn(b"\n", data.replace(b"\r\n", b""), entry)
                        self.assertIn(b"\r\n", data, entry)
                    else:
                        # A rewritten binary would be silently corrupt.
                        self.assertEqual(data, (HERE / source_name).read_bytes(), entry)
            expected = sorted([entry for _, entry in build_delivery.PAYLOAD]
                              + [build_delivery.ASAR_ENTRY])
            self.assertEqual(sorted(names), expected)
            self.assertTrue(any(name.startswith(build_delivery.CLEAN_FOLDER + "/")
                                for name in names))
            self.assertTrue(any(name.startswith(build_delivery.CANDIDATE_FOLDER + "/")
                                for name in names))


if __name__ == "__main__":
    unittest.main()
