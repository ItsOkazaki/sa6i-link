"""Tests for the source-equivalence comparison (no builds, no binaries)."""
import json
from pathlib import Path
import tempfile
import unittest

import verify_upstream_equivalence as verify


def write(root, name, data):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))


class EquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.root = Path(self.work.name)
        self.expected, self.actual = self.root / 'expected', self.root / 'actual'
        self.expected.mkdir()
        self.actual.mkdir()

    def tearDown(self):
        self.work.cleanup()

    def both(self, name, data, other=None):
        write(self.expected, name, data)
        write(self.actual, name, data if other is None else other)

    def test_identical_tree_matches(self):
        self.both('dist/assets/app.js', 'console.log(1)')
        self.both('package.json', json.dumps({'name': 'sa6i-clean', 'productName': 'Sa6i Clean',
                                              'version': '0.2.0', 'main': 'dist-electron/main.js',
                                              'type': 'module', 'scripts': {'dev': 'vite'}}),
                  json.dumps({'name': 'sa6i-clean', 'productName': 'Sa6i Clean', 'version': '0.2.0',
                              'main': 'dist-electron/main.js', 'type': 'module'}))
        self.both('dist/index.html', '<title>Sa6i Clean</title>\n')
        self.assertEqual(verify.compare(self.expected, self.actual), [])

    def test_changed_script_is_reported(self):
        self.both('dist-electron/main.js', 'a', 'b')
        self.assertTrue(any('content differs' in p for p in verify.compare(self.expected, self.actual)))

    def test_extra_file_is_reported(self):
        self.both('dist-electron/main.js', 'a')
        write(self.actual, 'dist/extra.js', 'x')
        self.assertTrue(any('unexpected packaged file' in p for p in verify.compare(self.expected, self.actual)))

    def test_identity_fields_must_match(self):
        self.both('package.json', json.dumps({'name': 'sa6i-clean', 'productName': 'Sa6i Clean',
                                              'version': '0.2.0', 'main': 'm.js', 'type': 'module'}),
                  json.dumps({'name': 'cleanly', 'productName': 'Sa6i Clean',
                              'version': '0.2.0', 'main': 'm.js', 'type': 'module'}))
        self.assertTrue(any('name' in p for p in verify.compare(self.expected, self.actual)))

    def test_blank_line_tolerated_but_content_change_not(self):
        self.both('dist/index.html', '<p>a</p>\n<p>b</p>\n', '<p>a</p>\n\n<p>b</p>\n')
        self.assertEqual(verify.compare(self.expected, self.actual), [])
        write(self.actual, 'dist/index.html', '<p>a</p>\n<p>c</p>\n')
        self.assertTrue(verify.compare(self.expected, self.actual))

    def test_source_pins_are_enforced(self):
        source = self.root / 'source'
        source.mkdir()
        with self.assertRaises(SystemExit):
            verify.check_source(source)


if __name__ == '__main__':
    unittest.main()
