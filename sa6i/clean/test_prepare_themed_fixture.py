"""Guardrails for the experimental cleaner design fixture."""
import tempfile
import unittest
from pathlib import Path

import prepare_themed_fixture as themed


class ThemedFixtureTests(unittest.TestCase):
    def test_unexpected_source_cannot_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / 'source', Path(tmp) / 'output'
            source.mkdir()
            (source / 'resources').mkdir()
            (source / themed.OUTPUT_NAME).write_bytes(b'not the pinned cleaner')
            (source / 'resources/app.asar').write_bytes(b'not the pinned asar')
            with self.assertRaises(ValueError):
                themed.prepare(source, output)
            self.assertFalse(output.exists())

    def test_rejects_existing_and_overlapping_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'
            source.mkdir()
            existing = Path(tmp) / 'existing'
            existing.mkdir()
            with self.assertRaises(FileExistsError):
                themed.prepare(source, existing)
            with self.assertRaises(ValueError):
                themed.prepare(source, source / 'nested')
            self.assertEqual(list(existing.iterdir()), [])

    def test_rejects_source_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'
            source.mkdir()
            try:
                (source / 'link').symlink_to(source, target_is_directory=True)
            except OSError:
                self.skipTest('No symlink support')
            with self.assertRaises(ValueError):
                themed.prepare(source, Path(tmp) / 'output')


if __name__ == '__main__':
    unittest.main()
