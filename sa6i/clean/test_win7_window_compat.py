"""Structural checks only; these do not establish Windows 7 behavior."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class Win7WindowCompatibilityTests(unittest.TestCase):
    def test_experiment_opt_in_disables_forced_no_redirection(self):
        source = (ROOT / 'desktop/app/cpp/app_helpers.cpp').read_text(encoding='utf-8')
        setup = source.split('void prepare_qt_without_log()', 1)[1].split('\n}', 1)[0]
        self.assertIn('#if SA6I_CLEAN_EXPERIMENT && defined(_WIN32)', setup)
        self.assertIn('qEnvironmentVariableIntValue("SA6I_CLEAN_WIN7_COMPAT") == 1', setup)
        self.assertIn('qputenv("QT_QPA_DISABLE_REDIRECTION_SURFACE", "0")', setup)
        self.assertIn('qputenv("QT_QPA_DISABLE_REDIRECTION_SURFACE", "1")', setup)

    def test_packaged_preview_launcher_opts_in(self):
        source = (ROOT / 'sa6i/clean/package_full_integration.py').read_text(encoding='utf-8')
        self.assertIn('set "SA6I_CLEAN_WIN7_COMPAT=1"', source)
        self.assertIn('set "SA6I_CLEAN_WIN7_SOFTWARE=1"', source)
        self.assertIn('set "QT_QUICK_BACKEND=software"', source)
        self.assertLess(source.index('set "SA6I_CLEAN_WIN7_COMPAT=1"'), source.index('start ""'))
        self.assertLess(source.index('set "SA6I_CLEAN_WIN7_SOFTWARE=1"'), source.index('start ""'))


if __name__ == '__main__':
    unittest.main()
