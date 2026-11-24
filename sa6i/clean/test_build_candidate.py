import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('build_candidate', Path(__file__).with_name('build_candidate.py'))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class CandidateBuilderTests(unittest.TestCase):
    def test_header_hash_matches_header_not_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.asar'
            path.write_bytes(struct.pack('<IIII', 4, 8, 4, 2) + b'{}' + b'body')
            import hashlib
            self.assertEqual(build.header_hash(path), hashlib.sha256(b'{}').hexdigest())

    def test_header_rejects_bad_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.asar'
            path.write_bytes(struct.pack('<IIII', 4, 8, 4, 0))
            with self.assertRaises(ValueError):
                build.header_hash(path)

    def test_replace_requires_exact_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'file'
            path.write_text('old old', encoding='utf-8')
            with self.assertRaises(ValueError):
                build.replace_exact(path, 'old', 'new', 1)
            self.assertEqual(path.read_text(), 'old old')
            build.replace_exact(path, 'old', 'new', 2)
            self.assertEqual(path.read_text(), 'new new')

    def test_icon_resources_are_checked_and_patched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'fixture.exe'
            with path.open('wb') as f:
                f.truncate(build.ICON_SLOTS[-1][0] + build.ICON_SLOTS[-1][1])
            group = bytearray(struct.pack('<HHH', 0, 1, len(build.ICON_SLOTS)))
            with path.open('r+b') as f:
                for index, (offset, size, size_field, dimension) in enumerate(build.ICON_SLOTS):
                    group.extend(struct.pack('<BBBBHHIH', dimension % 256, dimension % 256, 0, 0, 1, 32, size, index + 1))
                    f.seek(offset)
                    f.write(b'\x89PNG\r\n\x1a\n')
                    f.seek(size_field)
                    f.write(struct.pack('<I', size))
                f.seek(build.ICON_GROUP_OFFSET)
                f.write(group)
            build.patch_icons(path)
            with path.open('rb') as f:
                f.seek(build.ICON_GROUP_OFFSET)
                group = f.read(104)
                for index, (offset, _, size_field, dimension) in enumerate(build.ICON_SLOTS):
                    icon = (build.ASSETS / f'icon-{dimension}.png').read_bytes()
                    f.seek(offset)
                    self.assertEqual(f.read(len(icon)), icon)
                    f.seek(size_field)
                    self.assertEqual(struct.unpack('<I', f.read(4))[0], len(icon))
                    self.assertEqual(struct.unpack_from('<I', group, 6 + index * 14 + 8)[0], len(icon))
            with self.assertRaises(ValueError):
                build.patch_icons(path)  # already changed; do not patch an unknown layout

    def test_rejects_wrong_input_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'runtime').write_bytes(b'wrong')
            (tmp / 'exe').write_bytes(b'wrong')
            with self.assertRaises(ValueError):
                build.build(tmp / 'runtime', tmp / 'exe', tmp / 'output')
            self.assertFalse((tmp / 'output').exists())


if __name__ == '__main__':
    unittest.main()
