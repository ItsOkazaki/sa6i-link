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

    def test_visible_logo_uses_reviewed_embedded_artwork(self):
        build = (ROOT / "desktop/app/build.rs").read_text(encoding="utf-8")
        self.assertIn("../../sa6i/assets/windows/Square150x150Logo.png", build)
        self.assertIn(".qrc(branding_qrc())", build)
        for filename in ("MainWindow.qml", "pages/WelcomePage.qml"):
            with self.subTest(filename=filename):
                qml = (ROOT / "desktop/app/qml" / filename).read_text(encoding="utf-8")
                self.assertIn('source: "qrc:/branding/sa6i-link.png"', qml)

    def test_caption_icons_have_vector_fallback_when_fonts_are_missing(self):
        theme = (ROOT / "desktop/app/qml/Theme.qml").read_text(encoding="utf-8")
        captions = (ROOT / "desktop/app/qml/components/CaptionButtons.qml").read_text(encoding="utf-8")
        self.assertIn('Qt.fontFamilies().indexOf("Segoe MDL2 Assets") >= 0', theme)
        self.assertIn('"Segoe MDL2 Assets" : ""', theme)
        self.assertIn('Qt.platform.os === "windows" && Theme.captionIconFont.length > 0', captions)
        self.assertIn('visible: buttons.useFontGlyphs', captions)
        self.assertIn('visible: !buttons.useFontGlyphs', captions)

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
