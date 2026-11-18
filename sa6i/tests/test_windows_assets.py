"""Static checks for the separate Windows artwork candidate; not runtime tests."""
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('windows_assets', ROOT / 'sa6i/tools/package_windows_assets.py')
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


class WindowsAssetsTests(unittest.TestCase):
    def test_assets_are_png_and_correct_dimensions(self):
        for size in (44, 150):
            data = (ROOT / f'sa6i/assets/windows/Square{size}x{size}Logo.png').read_bytes()
            self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(struct.unpack('>II', data[16:24]), (size, size))

    def test_reject_unknown_input_without_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'input.zip'
            output = Path(tmp) / 'output.zip'
            with ZipFile(source, 'w') as z:
                z.writestr('other.txt', 'unrecognized')
            with self.assertRaises(ValueError):
                patch.package(source, output)
            self.assertFalse(output.exists())

    def test_real_package_if_available(self):
        source = ROOT / 'google_drive/Sa6i Link.zip'
        if not source.exists():
            self.skipTest('External release ZIP not present')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'candidate.zip'
            patch.package(source, output)
            with ZipFile(source) as old, ZipFile(output) as new:
                self.assertEqual(old.namelist(), new.namelist())
                changed = {n for n in old.namelist() if old.read(n) != new.read(n)}
                self.assertEqual(changed, set(patch.ASSETS))
                self.assertIsNone(new.testzip())
            with self.assertRaises(FileExistsError):
                patch.package(source, output)


if __name__ == '__main__':
    unittest.main()
