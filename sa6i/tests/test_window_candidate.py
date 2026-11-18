"""Static checks for the experimental v8 title-bar workaround; not runtime tests."""

import importlib.util
import struct
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("window_candidate", ROOT / "sa6i/tools/package_window_candidate.py")
patch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patch)
BASELINE = ROOT / "sa6i/baseline/windows-arabic-v8"


class WindowCandidateTests(unittest.TestCase):
    def test_app_patch_is_bounded_and_windows_11_only(self):
        original = (BASELINE / "Sa6i-Link-Win7-UI-v8.exe").read_bytes()
        result = patch.patched_app(original)
        start = patch.QML_OFFSET - 8
        end = patch.QML_OFFSET + patch.QML_CAPACITY
        self.assertEqual(original[:start], result[:start])
        self.assertEqual(original[end:], result[end:])
        n = struct.unpack_from(">I", result, patch.QML_OFFSET - 8)[0] - 4
        qml = zlib.decompress(result[patch.QML_OFFSET:patch.QML_OFFSET + n]).decode("utf-8")
        self.assertIn('Qt.platform.os === "windows" && window.systemBackdropSupported', qml)
        self.assertIn('~Qt.ExpandedClientAreaHint) | Qt.FramelessWindowHint', qml)

    def test_launcher_only_changes_target_string(self):
        original = (BASELINE / "Start Sa6i Link v8.exe").read_bytes()
        result = patch.patched_launcher(original)
        self.assertEqual(len(original), len(result))
        self.assertIn("%ls\\Sa6i Link App.exe".encode("utf-16le"), result)
        with self.assertRaises(ValueError):
            patch.patched_launcher(result)


if __name__ == "__main__":
    unittest.main()
