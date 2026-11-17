"""Static checks for the preserved v8 binary, not Windows runtime tests."""

import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXE = ROOT / "sa6i/baseline/windows-arabic-v8/Sa6i-Link-Win7-UI-v8.exe"


class V8PatchBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = EXE.read_bytes()

    def test_reviewed_binary_hash(self):
        self.assertEqual(
            hashlib.sha256(self.data).hexdigest(),
            "f2a7598aa067eb1ed19628e73b8c958d97db3bb8e09c424a6ab14f393e33d19c",
        )

    def test_v3_compatibility_patch_markers(self):
        # Marker bytes from patcher-v3.c in the supplied original folder.
        expected = {
            0xF04A27: bytes.fromhex("e81362bf0090"),
            0xA605FD: bytes.fromhex("e83da6090190"),
            0x1AFAC3F: bytes.fromhex("b801400080c3"),
            0x1CE1888: b"QT_QPA_DISABLE_REDIRECTION_SURFACX",
        }
        for offset, marker in expected.items():
            with self.subTest(offset=hex(offset)):
                self.assertEqual(self.data[offset : offset + len(marker)], marker)

    def test_old_and_new_import_thunks_were_rebound(self):
        for offset, left, right in [
            (0x24EEDC8, 0, 8), (0x1AFC8B8, 0, 8),
            (0x24EF310, 0, 8), (0x1AFCE00, 0, 8),
        ]:
            with self.subTest(offset=hex(offset)):
                self.assertEqual(
                    self.data[offset + left : offset + left + 8],
                    self.data[offset + right : offset + right + 8],
                )


if __name__ == "__main__":
    unittest.main()
