"""Source checks only; these do not build or validate an Android APK."""
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / 'android/app/src/main/res'
UPDATER_KEYS = {
    'update_title', 'update_not_allowed', 'update_up_to_date_version',
    'update_current_version', 'update_ready_title', 'update_done_title',
}


class AndroidRebrandStringsTest(unittest.TestCase):
    def test_update_strings_do_not_show_old_brand(self):
        for path in RES.glob('values*/strings.xml'):
            tree = ET.parse(path)
            for element in tree.getroot().findall('string'):
                if element.get('name') in UPDATER_KEYS:
                    with self.subTest(file=path, key=element.get('name')):
                        self.assertNotRegex(''.join(element.itertext()), re.compile('sa6i-link', re.I))

    def test_new_download_path_and_legacy_provider(self):
        for path in RES.glob('values*/strings.xml'):
            root = ET.parse(path).getroot()
            for key in ('transfer_received_from', 'guide_files_privacy'):
                element = root.find(f"string[@name='{key}']")
                if element is not None:
                    with self.subTest(file=path, key=key):
                        self.assertIn('Sa6i Link', ''.join(element.itertext()))
                        self.assertNotIn('Sa6iLink', ''.join(element.itertext()))
        provider = (RES / 'xml/file_paths.xml').read_text(encoding='utf-8')
        self.assertIn('path="Download/Sa6i Link/"', provider)
        self.assertIn('path="Download/Sa6iLink/"', provider)
        received = (ROOT / 'android/app/src/main/kotlin/app/sa6i-link/android/files/ReceivedFiles.kt').read_text(encoding='utf-8')
        self.assertEqual(received.count('"Sa6i Link"'), 2)
        self.assertNotIn('"Sa6iLink"', received)

    def test_upstream_updater_disabled_in_source(self):
        source = (ROOT / 'android/app/src/main/kotlin/app/sa6i-link/android/update/AppUpdater.kt').read_text(encoding='utf-8')
        self.assertIn('val enabled: Boolean get() = false', source)


class AndroidKotlinRebrandTest(unittest.TestCase):
    def test_selected_display_names_in_source(self):
        base = ROOT / 'android/app/src/main/kotlin/app/sa6i-link/android'
        checks = {
            'media/PcMedia.kt': ('"Sa6i Link PC media"', '"Sa6i Link PC media"'),
            'core/Core.kt': ('"not a Sa6i Link code"', '"not a Sa6i Link code"'),
            'clipboard/PhoneClipboard.kt': ('"Sa6i Link file"', '"Sa6i Link file"'),
        }
        for name, (new, old) in checks.items():
            with self.subTest(file=name):
                text = (base / name).read_text(encoding='utf-8')
                self.assertIn(new, text)
                self.assertNotIn(old, text)


if __name__ == '__main__':
    unittest.main()
