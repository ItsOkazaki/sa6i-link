"""Offline APK structure checks; no Android runtime or cryptographic verification."""
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('android_candidate', ROOT / 'sa6i/tools/package_android_branding_candidate.py')
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


class AndroidCandidateTest(unittest.TestCase):
    def test_reject_unknown_input_before_running_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name in ('bad.apk', 'bad.jar', 'bad-signer.jar'):
                (p / name).write_bytes(b'wrong')
            output = p / 'out.apk'
            with self.assertRaises(ValueError):
                patch.package(p / 'bad.apk', output, 'java', 'keytool', p / 'bad.jar', p / 'bad-signer.jar')
            self.assertFalse(output.exists())

    def test_candidate_if_present(self):
        source = ROOT / 'google_drive/Sa6i Link.apk'
        candidate = ROOT / 'google_drive/Sa6i Link - Android Branding Test.apk'
        if not source.is_file() or not candidate.is_file():
            self.skipTest('External test APK and baseline not present')
        with ZipFile(source) as src, ZipFile(candidate) as dst:
            self.assertIsNone(dst.testzip())
            for info in src.infolist():
                if info.filename not in patch.OLD_SIGNATURES and info.filename != 'classes.dex':
                    self.assertEqual(src.read(info), dst.read(info.filename), info.filename)
            dex = dst.read('classes.dex')
            for changes in patch.CHANGES.values():
                for old, new in changes:
                    self.assertIn(new.encode(), dex)
                    self.assertNotIn(old.encode(), dex)
            for info in dst.infolist():
                if info.compress_type == ZIP_STORED:
                    with candidate.open('rb') as f:
                        f.seek(info.header_offset + 26)
                        n, x = struct.unpack('<HH', f.read(4))
                    alignment = 16384 if info.filename.startswith('lib/') and info.filename.endswith('.so') else 4
                    self.assertEqual((info.header_offset + 30 + n + x) % alignment, 0, info.filename)


if __name__ == '__main__':
    unittest.main()
