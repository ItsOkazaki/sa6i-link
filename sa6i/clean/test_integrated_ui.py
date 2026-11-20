"""Tests of the exact, experimental cleaner window-chrome transformation."""
import re
import tempfile
import unittest
from pathlib import Path

import prepare_integrated_ui as ui
import prepare_full_integration as full

ROOT = Path(__file__).resolve().parents[2]


class IntegratedUiTests(unittest.TestCase):
    def test_window_patch_preserves_other_code_and_removes_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / 'main.js'
            original = 'before;' + ui.WINDOW_OPTIONS + ';middle;' + ui.THEME_OVERLAY + ';after'
            main.write_text(original, encoding='utf-8')
            ui.patch_main(main)
            self.assertEqual(main.read_text(encoding='utf-8'),
                             'before;' + ui.FRAMELESS_OPTIONS + ';middle;void 0;after')
            with self.assertRaises(ValueError):
                ui.patch_main(main)

    def test_unexpected_source_cannot_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'
            source.mkdir()
            (source / 'resources').mkdir()
            (source / 'Sa6i Clean.exe').write_bytes(b'wrong')
            (source / 'resources/app.asar').write_bytes(b'wrong')
            output = Path(tmp) / 'output'
            with self.assertRaises(ValueError):
                ui.prepare(source, output)
            self.assertFalse(output.exists())

    def test_full_fixture_pins_match_native_host_and_ci(self):
        text = (ROOT / 'sa6i/clean/native_embed.c').read_text(encoding='utf-8')
        block = text.split('#if SA6I_CLEAN_FULL_FIXTURE', 1)[1].split('#else', 1)[0]
        arrays = re.findall(r'static const BYTE expected_(?:exe|asar)\[32\] = \{([^}]+)\}', block)
        self.assertEqual(len(arrays), 2)
        actual = [bytes(int(n, 16) for n in re.findall(r'0x([0-9a-fA-F]{2})', arr)).hex() for arr in arrays]
        self.assertEqual(actual, [full.OUTPUT_SHA, full.ASAR_SHA])
        workflow = (ROOT / '.github/workflows/sa6i-clean-win7-build.yml').read_text(encoding='utf-8')
        self.assertIn(full.OUTPUT_SHA, workflow)
        self.assertIn(full.ASAR_SHA, workflow)
        smoke_helper = (ROOT / 'sa6i/clean/tests/prepare_synthetic_desktop.py').read_text(encoding='utf-8')
        self.assertIn(full.OUTPUT_SHA, smoke_helper)
        self.assertIn(full.ASAR_SHA, smoke_helper)


if __name__ == '__main__':
    unittest.main()
