"""Tests of the exact, experimental cleaner window-chrome transformation."""
import re
import tempfile
import unittest
from pathlib import Path

import prepare_integrated_ui as ui
import remove_support_navigation as cleaner

ROOT = Path(__file__).resolve().parents[2]


class IntegratedUiTests(unittest.TestCase):
    def test_clean_entry_uses_title_action_row_and_welcome_fallback(self):
        # Source-level regression: the normal entry must participate in the
        # same Row as Refresh, not be absolutely positioned over that Row.
        main = (ROOT / 'desktop/app/qml/MainWindow.qml').read_text(encoding='utf-8')
        integration = (ROOT / 'desktop/app/qml/components/Sa6iCleanIntegration.qml').read_text(encoding='utf-8')
        actions = main.split('id: topBarActions', 1)[1].split('id: pages', 1)[0]
        self.assertIn('id: cleanTopBtn', actions)
        self.assertIn('id: refresh', actions)
        self.assertIn('iconPath: Icons.sparkle', actions)
        self.assertIn('sa6iCleanLoader.item.openClean()', actions)
        self.assertIn('id: welcomeCleanBtn', main)
        self.assertIn('visible: window.welcome && !window.hubActive && !!sa6iCleanLoader.item', main)
        self.assertNotIn('CleanEntry {', integration)
        self.assertNotIn('anchors.rightMargin: 160', integration)

    def test_hub_shell_keeps_link_and_clean_navigation_separate(self):
        main = (ROOT / 'desktop/app/qml/MainWindow.qml').read_text(encoding='utf-8')
        welcome = (ROOT / 'desktop/app/qml/pages/WelcomePage.qml').read_text(encoding='utf-8')
        integration = (ROOT / 'desktop/app/qml/components/Sa6iCleanIntegration.qml').read_text(encoding='utf-8')
        self.assertIn('title: "Sa6i Hub"', main)
        self.assertIn('qsTr("Link") + " · "', main)
        self.assertIn('topBarActions.x - x - 12', main)
        self.assertIn('Welcome to Sa6i Hub', welcome)
        self.assertIn('Sa6i Link to connect your phone', welcome)
        self.assertIn('sa6iCleanLoader.item.openClean()', main)
        self.assertIn('Back to Sa6i Link', integration)
        self.assertIn('function requestClose(action)', integration)

    def test_dashboard_and_back_paths_keep_link_and_clean_coordinated(self):
        main = (ROOT / 'desktop/app/qml/MainWindow.qml').read_text(encoding='utf-8')
        integration = (ROOT / 'desktop/app/qml/components/Sa6iCleanIntegration.qml').read_text(encoding='utf-8')
        self.assertIn('property bool hubActive: true', main)
        self.assertIn('objectName: "hubHome"', main)
        self.assertIn('objectName: "hubOpenLink"', main)
        self.assertIn('objectName: "hubOpenClean"', main)
        self.assertIn('objectName: "hubFromLinkButton"', main)
        self.assertIn('objectName: "hubFromWelcomeButton"', main)
        self.assertIn('onBackRequested: window.hubActive = true', main)
        self.assertIn('visible: !window.welcome && !window.hubActive', main)
        self.assertIn('MouseArea { anchors.fill: parent }', main)
        self.assertIn('function goBack()', integration)
        self.assertIn('cleanOpen = false', integration)
        self.assertIn('backRequested()', integration)
        self.assertIn('Keys.onReturnPressed: root.goBack()', integration)
        self.assertIn('onClicked: root.goBack()', integration)

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
        self.assertEqual(actual, [cleaner.OUTPUT_EXE_SHA, cleaner.OUTPUT_ASAR_SHA])
        workflow = (ROOT / '.github/workflows/sa6i-clean-win7-build.yml').read_text(encoding='utf-8')
        self.assertIn(cleaner.OUTPUT_EXE_SHA, workflow)
        self.assertIn(cleaner.OUTPUT_ASAR_SHA, workflow)
        smoke_helper = (ROOT / 'sa6i/clean/tests/prepare_synthetic_desktop.py').read_text(encoding='utf-8')
        self.assertIn(cleaner.OUTPUT_EXE_SHA, smoke_helper)
        self.assertIn(cleaner.OUTPUT_ASAR_SHA, smoke_helper)


if __name__ == '__main__':
    unittest.main()
