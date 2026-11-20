"""Package assembly tests use inert tiny fixtures, never real cleaner binaries."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import package_full_integration as pack


def digest(data):
    return hashlib.sha256(data).hexdigest()


class FullPackageTests(unittest.TestCase):
    def test_package_includes_only_verified_app_local_shim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            desktop, cleaner, output = root / 'desktop', root / 'cleaner', root / 'output'
            desktop.mkdir()
            (cleaner / 'resources').mkdir(parents=True)
            fixture_exe, fixture_asar, shim = b'inert exe', b'inert asar', b'inert shim'
            exe_hash, asar_hash = digest(fixture_exe), digest(fixture_asar)
            (desktop / 'nectarlink-desktop.exe').write_bytes(
                pack.OUTPUT_NAME.encode('utf-16le') + bytes.fromhex(exe_hash) + bytes.fromhex(asar_hash))
            (desktop / 'Qt6Core.dll').write_bytes(b'not Qt')
            (cleaner / pack.OUTPUT_NAME).write_bytes(fixture_exe)
            (cleaner / 'resources/app.asar').write_bytes(fixture_asar)
            shim_path = root / 'cldapi.dll'
            shim_path.write_bytes(shim)
            with patch.object(pack, 'OUTPUT_SHA', exe_hash), patch.object(pack, 'ASAR_SHA', asar_hash), \
                 patch.object(pack, 'WIN7_SHIM_SHA', digest(shim)):
                pack.package(desktop, cleaner, output, shim_path)
                self.assertEqual((output / 'cldapi.dll').read_bytes(), shim)
                self.assertIn('disables phone-storage', (output / 'READ FIRST - EXPERIMENT.txt').read_text())
                software = (output / 'Start Integrated Test.cmd').read_text()
                standard = (output / 'Start Integrated Standard Rendering.cmd').read_text()
                self.assertIn('set "SA6I_CLEAN_WIN7_COMPAT=1"', standard)
                self.assertIn('set "SA6I_CLEAN_WIN7_SOFTWARE="', standard)
                self.assertIn('set "QT_QUICK_BACKEND="', standard)
                self.assertIn('set "SA6I_CLEAN_WIN7_SOFTWARE=1"', software)
                self.assertIn('set "QT_QUICK_BACKEND=software"', software)
                self.assertIn('Sa6i-Link-Integrated-Standard-', standard)
                self.assertIn('Sa6i-Link-Integrated-Test-', software)
                with self.assertRaises(FileExistsError):
                    pack.package(desktop, cleaner, output, shim_path)
                (desktop / 'cldapi.dll').write_bytes(b'unexpected')
                with self.assertRaises(ValueError):
                    pack.package(desktop, cleaner, root / 'bad-output', shim_path)
                self.assertFalse((root / 'bad-output').exists())

    def test_rejects_unknown_shim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shim = root / 'cldapi.dll'
            shim.write_bytes(b'not the original shim')
            with self.assertRaises(ValueError):
                pack.package(root / 'desktop', root / 'cleaner', root / 'output', shim)
            self.assertFalse((root / 'output').exists())


if __name__ == '__main__':
    unittest.main()
