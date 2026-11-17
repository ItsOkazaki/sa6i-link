"""Checks for the source-level Sa6i Link labels."""

import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class BrandingTests(unittest.TestCase):
    def test_android_app_name_in_every_locale(self):
        for path in (ROOT / "android/app/src/main/res").glob("values*/strings.xml"):
            with self.subTest(path=path):
                root = ET.parse(path).getroot()
                label = root.find("string[@name='app_name']")
                if label is not None:
                    self.assertEqual(label.text, "Sa6i Link")

    def test_qml_branded_labels_keep_arabic_translation_keys(self):
        catalogue = ET.parse(ROOT / "desktop/app/i18n/nectarlink_ar.ts")
        sources = {entry.text for entry in catalogue.iter("source")}
        pattern = re.compile(
            r'qsTr\("((?:[^"\\]|\\.)*NectarLink(?:[^"\\]|\\.)*)"\)'
            r'\.replace\(/NectarLink/g, "Sa6i Link"\)'
        )
        matches = []
        for path in (ROOT / "desktop/app/qml").rglob("*.qml"):
            matches.extend(pattern.findall(path.read_text(encoding="utf-8")))
        self.assertGreater(len(matches), 0)
        for source in matches:
            with self.subTest(source=source):
                self.assertIn(source, sources)


if __name__ == "__main__":
    unittest.main()
