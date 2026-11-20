"""Integrity verifier tests use small inert ZIPs, not executable fixtures."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

import verify_clearance_preview as check


def create_zip(path, entries):
    with ZipFile(path, 'w') as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return hashlib.sha256(path.read_bytes()).hexdigest()


class VerifyPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.base, self.update, self.folder = root / 'base.zip', root / 'update.zip', root / 'preview'
        self.folder.mkdir()
        self.base_hash = create_zip(self.base, [
            (check.BASE_ROOT + 'app.exe', b'old'),
            (check.BASE_ROOT + 'Sa6i Clean/resources/app.asar', b'fixture'),
        ])
        self.update_hash = create_zip(self.update, [('app.exe', b'new'), ('START.cmd', b'launch')])
        (self.folder / 'Sa6i Clean/resources').mkdir(parents=True)
        (self.folder / 'Sa6i Clean/resources/app.asar').write_bytes(b'fixture')
        (self.folder / 'app.exe').write_bytes(b'new')
        (self.folder / 'START.cmd').write_bytes(b'launch')
        self.patches = [patch.object(check, 'BASE_SHA256', self.base_hash),
                        patch.object(check, 'UPDATE_SHA256', self.update_hash)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_complete_overlay_and_discrepancies(self):
        self.assertEqual(check.verify(self.base, self.update, self.folder), [])
        (self.folder / 'app.exe').write_bytes(b'bad')
        (self.folder / 'START.cmd').unlink()
        (self.folder / 'extra').write_bytes(b'extra')
        errors = check.verify(self.base, self.update, self.folder)
        self.assertIn('Different: app.exe', errors)
        self.assertIn('Missing: START.cmd', errors)
        self.assertIn('Unexpected: extra', errors)

    def test_unknown_archive_rejected(self):
        self.update.write_bytes(b'not the pinned archive')
        with self.assertRaisesRegex(ValueError, 'Unknown archive'):
            check.verify(self.base, self.update, self.folder)

    def test_archive_traversal_duplicate_and_symlink_rejected(self):
        for entries in [
            [('..\\outside', b'x')], [('../outside', b'x')],
            [('a', b'x'), ('A', b'y')],
        ]:
            with self.subTest(entries=entries):
                digest = create_zip(self.update, entries)
                with patch.object(check, 'UPDATE_SHA256', digest):
                    with self.assertRaises(ValueError):
                        check.verify(self.base, self.update, self.folder)
        link = ZipInfo('link')
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        digest = create_zip(self.update, [(link, 'target')])
        with patch.object(check, 'UPDATE_SHA256', digest):
            with self.assertRaisesRegex(ValueError, 'symbolic link'):
                check.verify(self.base, self.update, self.folder)

    def test_filesystem_symlink_reported(self):
        target = self.folder / 'app.exe'
        target.unlink()
        try:
            target.symlink_to(self.folder / 'START.cmd')
        except OSError:
            self.skipTest('symlinks unavailable')
        errors = check.verify(self.base, self.update, self.folder)
        self.assertIn('Symbolic link: app.exe', errors)
        self.assertIn('Missing: app.exe', errors)


if __name__ == '__main__':
    unittest.main()
