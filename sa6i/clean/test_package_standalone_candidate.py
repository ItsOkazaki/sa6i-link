"""Standalone assembler tests use inert fixtures and never execute binaries."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import package_standalone_candidate as pack


def sha(data):
    return hashlib.sha256(data).hexdigest()


def make_zip(path, files, prefix=''):
    with ZipFile(path, 'w') as out:
        for name, data in files.items():
            out.writestr(prefix + name, data)
    return sha(path.read_bytes())


class StandaloneCandidateTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        root = Path(self.work.name)
        self.base, self.speed, self.output = root / 'base.zip', root / 'speed.zip', root / 'out.zip'
        self.files = {
            'Sa6i Clean/Sa6i Clean Integration.exe': b'cleaner',
            'Sa6i Clean/resources/app.asar': b'asar',
            'Sa6i Clean/LICENSE.electron.txt': b'notice',
            'cldapi.dll': b'shim',
            'sa6i-link.exe': b'old desktop',
            'sa6i_link_vcam.dll': b'old vcam',
            'Start Integrated Test.cmd': b'old launcher',
            'Start Win7 Compatibility Test.cmd': b'old launcher',
            'READ FIRST - EXPERIMENT.txt': b'old readme',
            'INTEGRATION-BUILD-ONLY.txt': b'old notice',
        }
        self.update = {
            'sa6i-link.exe': b'new desktop',
            'sa6i_link_vcam.dll': b'new vcam',
            'Start Reopen Speed Test.cmd': b'@echo off\r\nset "SA6I_DATA=old"\r\nstart app --sa6i-clean-header-clearance\r\n',
        }
        base_hash = make_zip(self.base, self.files, pack.BASE_ROOT)
        speed_hash = make_zip(self.speed, self.update)
        self.patcher = patch.multiple(pack, BASE_SHA=base_hash, SPEED_SHA=speed_hash,
            CLEAN_EXE_SHA=sha(b'cleaner'), CLEAN_ASAR_SHA=sha(b'asar'), SHIM_SHA=sha(b'shim'),
            DESKTOP_SHA=sha(b'new desktop'), VCAM_SHA=sha(b'new vcam'))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.base_bytes, self.speed_bytes = self.base.read_bytes(), self.speed.read_bytes()

    def test_combines_exact_binaries_and_preserves_notices(self):
        self.assertEqual(pack.build(self.base, self.speed, self.output), self.output)
        self.assertEqual(self.base.read_bytes(), self.base_bytes)
        self.assertEqual(self.speed.read_bytes(), self.speed_bytes)
        with ZipFile(self.output) as result:
            self.assertIsNone(result.testzip())
            self.assertTrue(all(info.extract_version <= 20 for info in result.infolist()))
            read = lambda name: result.read(pack.OUT_ROOT + name)
            self.assertEqual(read('sa6i-link.exe'), b'new desktop')
            self.assertEqual(read('sa6i_link_vcam.dll'), b'new vcam')
            self.assertEqual(read('Sa6i Clean/resources/app.asar'), b'asar')
            self.assertEqual(read('Sa6i Clean/LICENSE.electron.txt'), b'notice')
            self.assertNotIn(pack.OUT_ROOT + 'Start Integrated Test.cmd', result.namelist())
            self.assertNotIn(pack.OUT_ROOT + 'Start Win7 Compatibility Test.cmd', result.namelist())
            launcher = read('Start Sa6i Link Candidate.cmd')
            self.assertIn(b'--sa6i-clean-header-clearance', launcher)
            self.assertIn(b'Sa6i-Link-Candidate-', launcher)
            self.assertNotIn(b'SA6I_DATA=old', launcher)
            self.assertIn(b'NOT a sandbox', read('READ FIRST - CANDIDATE.txt'))
        with self.assertRaises(FileExistsError):
            pack.build(self.base, self.speed, self.output)

    def test_rejects_unknown_and_incompatible_without_output(self):
        self.speed.write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError, 'Unrecognized'):
            pack.build(self.base, self.speed, self.output)
        self.assertFalse(self.output.exists())
        self.speed.write_bytes(self.speed_bytes)
        with patch.object(pack, 'CLEAN_ASAR_SHA', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'component'):
                pack.build(self.base, self.speed, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_is_never_replaced(self):
        self.output.write_bytes(b'existing')
        with self.assertRaises(FileExistsError):
            pack.build(self.base, self.speed, self.output)
        self.assertEqual(self.output.read_bytes(), b'existing')

    def test_malformed_launcher_is_rejected(self):
        self.update['Start Reopen Speed Test.cmd'] = b'no required flags'
        digest = make_zip(self.speed, self.update)
        with patch.object(pack, 'SPEED_SHA', digest):
            with self.assertRaisesRegex(ValueError, 'launcher'):
                pack.build(self.base, self.speed, self.output)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
