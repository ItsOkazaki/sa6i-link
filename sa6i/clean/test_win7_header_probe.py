import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'google_drive/Sa6i Clean - Host Test/Sa6i Clean.exe'
SOURCE_HASH = 'ca539c306d32921f9caa9b55e2fd8ee77e0b44fbf3cfd81c70663a205e993049'
OUTPUT_HASH = '883933449d343dec5925e9068c7e81052678a186af718ff6a07c15d6bbb38abe'


class HeaderProbeTests(unittest.TestCase):
    @unittest.skipUnless(INPUT.is_file(), 'restricted fixture unavailable')
    def test_only_header_bytes_are_changed(self):
        source_hash = hashlib.sha256()
        output_hash = hashlib.sha256()
        count = 0
        with INPUT.open('rb') as f:
            for offset in range(0, INPUT.stat().st_size, 1024 * 1024):
                chunk = f.read(1024 * 1024)
                source_hash.update(chunk)
                patched = bytearray(chunk)
                for pos in (184, 192):
                    if offset <= pos < offset + len(chunk):
                        i = pos - offset
                        self.assertEqual(patched[i:i + 4], b'\x0a\x00\x00\x00')
                        patched[i:i + 4] = b'\x06\x00\x01\x00'
                        count += 1
                output_hash.update(patched)
        self.assertEqual(count, 2)
        self.assertEqual(source_hash.hexdigest(), SOURCE_HASH)
        self.assertEqual(output_hash.hexdigest(), OUTPUT_HASH)


if __name__ == '__main__':
    unittest.main()
