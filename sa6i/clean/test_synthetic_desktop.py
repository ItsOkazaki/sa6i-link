"""The fixture pin patcher must never modify its source desktop."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).parent / 'tests' / 'prepare_synthetic_desktop.py'
spec = importlib.util.spec_from_file_location('prepare_synthetic_desktop', MODULE_PATH)
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class SyntheticDesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.fixture = root / 'fixture'
        (self.fixture / 'resources').mkdir(parents=True)
        (self.fixture / 'Sa6i Clean Integration.exe').write_bytes(b'harmless executable')
        (self.fixture / 'resources/app.asar').write_bytes(b'harmless asar')
        self.desktop = root / 'desktop.exe'
        self.output = root / 'synthetic-test-desktop.exe'
        self.original = (b'header' + 'Sa6i Clean Integration.exe'.encode('utf-16le') +
                         bytes.fromhex(patcher.THEMED_PINS[0][0]) + b'between' +
                         bytes.fromhex(patcher.THEMED_PINS[1][0]) + b'end')
        self.desktop.write_bytes(self.original)

    def test_only_copy_has_fixture_hashes(self):
        patcher.main(self.desktop, self.fixture, digest(self.original), patcher.THEMED_PINS)
        self.assertEqual(self.desktop.read_bytes(), self.original)
        result = self.output.read_bytes()
        for old, name in patcher.THEMED_PINS:
            self.assertNotIn(bytes.fromhex(old), result)
            self.assertEqual(result.count(bytes.fromhex(digest((self.fixture / name).read_bytes()))), 1)
        self.assertEqual(len(result), len(self.original))
        with self.assertRaisesRegex(SystemExit, 'overwrite'):
            patcher.main(self.desktop, self.fixture, digest(self.original), patcher.THEMED_PINS)

    def test_refuses_wrong_hash_missing_or_duplicate_pins(self):
        with self.assertRaisesRegex(SystemExit, 'does not match'):
            patcher.main(self.desktop, self.fixture, '0' * 64, patcher.THEMED_PINS)
        for data in (self.original + bytes.fromhex(patcher.THEMED_PINS[0][0]),
                     self.original.replace(bytes.fromhex(patcher.THEMED_PINS[1][0]), b'x' * 32)):
            self.desktop.write_bytes(data)
            with self.assertRaisesRegex(SystemExit, 'exactly one pin'):
                patcher.main(self.desktop, self.fixture, digest(data), patcher.THEMED_PINS)
            self.assertFalse(self.output.exists())
            self.assertEqual(self.desktop.read_bytes(), data)


if __name__ == '__main__':
    unittest.main()
