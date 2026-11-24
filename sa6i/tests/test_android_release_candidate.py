"""Offline tests for the version-locked release candidate; not device tests."""
import importlib.util
import struct
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('android_release', ROOT / 'sa6i/tools/package_android_release_candidate.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def synthetic_table(count=10):
    strings = [f'Download/Sa6iLink {i}' for i in range(count)] + ['unchanged']
    payload, offsets = bytearray(), []
    for s in strings:
        raw = s.encode()
        offsets.append(len(payload))
        payload.extend(bytes([len(s), len(raw)]) + raw + b'\0')
    payload.extend(b'\0' * (-len(payload) % 4))
    start = 28 + 4 * len(strings)
    pool = struct.pack('<HHIIIIII', 1, 28, start + len(payload), len(strings), 0, 0x100, start, 0)
    pool += b''.join(struct.pack('<I', i) for i in offsets) + payload
    package = b'package chunk unchanged'
    return struct.pack('<HHII', 2, 12, 12 + len(pool) + len(package), 1) + pool + package


class ReleaseCandidateTest(unittest.TestCase):
    def test_resource_pool_only_replaces_expected_strings(self):
        old = synthetic_table()
        new = release.patch_resource_table(old)
        self.assertEqual(new.count(b'Download/Sa6i Link'), 10)
        self.assertNotIn(b'Download/Sa6iLink', new)
        self.assertIn(b'unchanged\0', new)
        self.assertTrue(new.endswith(b'package chunk unchanged'))
        self.assertEqual(struct.unpack_from('<I', new, 4)[0], len(new))

    def test_resource_pool_rejects_unexpected_input(self):
        with self.assertRaises(ValueError):
            release.patch_resource_table(synthetic_table(9))

    def test_built_apk_if_present(self):
        source = ROOT / 'google_drive/Sa6i Link.apk'
        candidate = ROOT / 'google_drive/Sa6i Link - Signed Release Candidate.apk'
        if not source.exists() or not candidate.exists():
            self.skipTest('External APKs not present')
        with ZipFile(source) as src, ZipFile(candidate) as dst:
            self.assertIsNone(dst.testzip())
            for info in src.infolist():
                if info.filename in release.branding.OLD_SIGNATURES:
                    continue
                if info.filename not in {'classes.dex', 'resources.arsc', 'res/xml/file_paths.xml'}:
                    self.assertEqual(src.read(info), dst.read(info.filename), info.filename)
            self.assertEqual(dst.read('resources.arsc'), release.patch_resource_table(src.read('resources.arsc')))
            dex = dst.read('classes.dex')
            for changes in release.branding.CHANGES.values():
                for old, new in changes:
                    self.assertIn(new.encode(), dex)
                    self.assertNotIn(old.encode(), dex)
            for info in dst.infolist():
                if info.compress_type == ZIP_STORED:
                    with candidate.open('rb') as f:
                        f.seek(info.header_offset + 26)
                        n, extra = struct.unpack('<HH', f.read(4))
                    align = 16384 if info.filename.startswith('lib/') and info.filename.endswith('.so') else 4
                    self.assertEqual((info.header_offset + 30 + n + extra) % align, 0, info.filename)


if __name__ == '__main__':
    unittest.main()
