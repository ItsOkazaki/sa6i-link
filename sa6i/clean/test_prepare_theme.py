"""Draft renderer skin must be isolated from cleaner behavior."""
import tempfile
import unittest
from pathlib import Path

import prepare_theme


class PrepareThemeTests(unittest.TestCase):
    def test_only_html_and_design_assets_are_changed(self):
        with tempfile.TemporaryDirectory() as work:
            app = Path(work)
            assets = app / 'dist/assets'
            assets.mkdir(parents=True)
            html = app / 'dist/index.html'
            html.write_text('<head>\n' + prepare_theme.OLD_LINK + '\n</head>\n', encoding='utf-8')
            script = assets / 'index-BwXp8TnN.js'
            script.write_bytes(b'unchanged cleaner behavior')
            prepare_theme.apply_to_extracted(app)
            self.assertEqual(script.read_bytes(), b'unchanged cleaner behavior')
            self.assertIn(prepare_theme.NEW_LINK, html.read_text(encoding='utf-8'))
            for name in ('sa6i-integrated-theme.css', 'sa6i-figtree.ttf',
                         'sa6i-space-mono.ttf', 'sa6i-figtree-license.txt',
                         'sa6i-space-mono-license.txt'):
                self.assertTrue((assets / name).is_file())
            with self.assertRaises(ValueError):
                prepare_theme.apply_to_extracted(app)

    def test_reject_unexpected_renderer_without_writes(self):
        with tempfile.TemporaryDirectory() as work:
            app = Path(work)
            assets = app / 'dist/assets'
            assets.mkdir(parents=True)
            (app / 'dist/index.html').write_text('unknown renderer', encoding='utf-8')
            with self.assertRaises(ValueError):
                prepare_theme.apply_to_extracted(app)
            self.assertEqual(list(assets.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
