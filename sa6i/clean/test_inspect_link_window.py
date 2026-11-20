import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('inspect_link_window', Path(__file__).with_name('inspect_link_window.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InspectionTests(unittest.TestCase):
    def test_unknown_executable_is_rejected(self):
        with self.assertRaises(ValueError):
            module.extract_qml(b'not the known executable')

    def test_unknown_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'wrong.zip'
            path.write_bytes(b'not the known archive')
            with self.assertRaises(ValueError):
                module.inspect(path)

    def test_known_release_if_present(self):
        path = Path(__file__).resolve().parents[2] / 'google_drive' / 'Sa6i.Link.zip'
        if not path.exists():
            self.skipTest('User-provided release ZIP not present')
        data = module.inspect(path)
        self.assertEqual(hashlib.sha256(data).hexdigest(), module.QML_SHA)
        self.assertIn(b'NativeWindow', data)
        self.assertIn(b'window.systemBackdropSupported', data)


if __name__ == '__main__':
    unittest.main()
