#!/usr/bin/env python3
"""Check the cleaner debranding edits on a synthetic bundle."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import debrand_cleaner as debrand

BUNDLE = (
    'const nav=[(0,F.jsx)(`a`,{href:`#`}),'
    '(0,F.jsxs)(`button`,{type:`button`,className:`nav-item${e===`support`?` on`:``}`,'
    'onClick:()=>t(`support`),title:`Support Cleanly (original developer)`,'
    'children:[(0,F.jsx)(B,{name:`heart`}),`Tip`]}),'
    '(0,F.jsxs)(`button`,{type:`button`,className:`nav-item${e===`feedback`?` on`:``}`,'
    'onClick:()=>t(`feedback`),title:`Send feedback to the original Cleanly developer`,'
    'children:[(0,F.jsx)(B,{name:`chat`}),`Feedback`]}),'
    '(0,F.jsxs)(`button`,{type:`button`,className:`nav-item${e===`settings`?` on`:``}`,'
    'children:[`Settings`]})];'
    'const tip=`https://beyond-media.ai/tips?creator=beyond-apps`;'
    'const subject=`Cleanly feedback: idea`;'
    'const help=`The assistant inside Cleanly cannot read that.`;'
)


class DebrandTest(unittest.TestCase):
    def test_navigation_entries_are_removed_and_the_rest_survives(self):
        text, counts = debrand.debrand_text(BUNDLE)
        self.assertEqual(counts[debrand.NAV_MARKERS[0]], 1)
        self.assertEqual(counts[debrand.NAV_MARKERS[1]], 1)
        self.assertNotIn('Support Cleanly', text)
        self.assertNotIn('Send feedback to the original', text)
        self.assertNotIn('`Tip`', text)
        self.assertNotIn('`Feedback`', text)
        # The settings entry and the surrounding list are still intact.
        self.assertIn('`Settings`', text)
        # The settings entry closes the list; nothing else was disturbed.
        self.assertIn('`Settings`]})];', text)
        self.assertEqual(text.count('(0,F.jsxs)(`button`'), 1)

    def test_brand_words_and_outbound_links_are_rewritten(self):
        text, _ = debrand.debrand_text(BUNDLE)
        self.assertNotIn('Cleanly', text)
        self.assertIn('Sa6i Clean feedback: idea', text)
        self.assertNotIn('beyond-media.ai', text)
        self.assertIn('The assistant inside Sa6i Clean cannot read that.', text)

    def test_an_unexpected_layout_is_refused(self):
        with self.assertRaises(ValueError):
            debrand.debrand_text(BUNDLE.replace('`support`', '`donate`', 1))

    def test_a_tree_is_edited_in_place_only_in_the_copy(self):
        with TemporaryDirectory() as tmp:
            app = Path(tmp) / 'app'
            (app / 'dist/assets').mkdir(parents=True)
            (app / 'dist-electron').mkdir()
            (app / 'dist/assets/index-abc.js').write_text(BUNDLE, encoding='utf-8')
            (app / 'dist-electron/main.js').write_text(
                'const x=`Cleanly starts now`;', encoding='utf-8')
            out = Path(tmp) / 'out'
            counts = debrand.debrand(app, out)
            self.assertIn('dist/assets/index-abc.js', counts)
            self.assertNotIn('Cleanly', (out / 'dist/assets/index-abc.js').read_text())
            self.assertIn('Sa6i Clean', (out / 'dist-electron/main.js').read_text())
            self.assertIn('Support Cleanly', (app / 'dist/assets/index-abc.js').read_text())
            self.assertEqual(debrand.leftovers(out), [])


CHROME_JS = (
    'const nav=(0,F.jsxs)(`div`,{className:`brand`,children:[(0,F.jsx)(Ee,{}),'
    '(0,F.jsx)(`span`,{className:`brand-name`,children:`cleanly`})]});'
    'const about=(0,F.jsxs)(`div`,{children:[(0,F.jsx)(Ee,{size:44}),'
    '(0,F.jsx)(`h3`,{children:`cleanly`})]});'
    'const api=window.cleanly??re();'
    'const demo=[t(`cleanly`,1.4*f,`code`)];'
    'function Ee({size:e=30}){return(0,F.jsxs)(`svg`,{className:`brand-mark`,'
    'width:e,height:e,viewBox:`0 0 32 32`,"aria-hidden":`true`,'
    'children:[(0,F.jsx)(`path`,{d:`M16 2c1.2 7.4 6.6 12.8 14 14-7.4 1.2-12.8 '
    '6.6-14 14-1.2-7.4-6.6-12.8-14-14C9.4 14.8 14.8 9.4 16 2z`,'
    'fill:`url(#g-brand)`}),(0,F.jsx)(`circle`,{cx:`25`,cy:`7`,r:`2.4`,'
    'fill:`#ffb547`})]})}'
)


class ChromeTest(unittest.TestCase):
    """The parts of the interface the first pass left branded."""

    def test_lowercase_product_name_in_the_chrome_is_rewritten(self):
        counts = {}
        text = debrand.apply_brand(CHROME_JS, counts)
        self.assertNotRegex(text, '(?i)cleanly')
        self.assertEqual(counts['children:`cleanly`'], 2)
        self.assertEqual(text.count('children:`Sa6i Clean`'), 2)

    def test_client_api_and_channel_names_move_together(self):
        text = debrand.apply_brand(CHROME_JS, {})
        self.assertIn('window.sa6i', text)
        # Both ends of the bridge are in the same bundle set, so the rename is
        # consistent; what must not survive is the old spelling.
        self.assertNotIn('window.cleanly', text)

    def test_the_sparkle_logo_becomes_the_sa6i_clean_emblem(self):
        counts = {}
        text = debrand.apply_brand(CHROME_JS, counts)
        self.assertEqual(counts['brand mark'], 1)
        self.assertNotIn('#ffb547', text)
        self.assertNotIn('url(#g-brand)', text)
        self.assertIn('data:image/png;base64,', text)
        self.assertIn('className:`brand-mark`', text)
        # The replacement stays small enough to live in the bundle.
        self.assertLess(len(text) - len(CHROME_JS), 60000)

    def test_window_title_and_package_metadata_are_rewritten(self):
        with TemporaryDirectory() as tmp:
            app = Path(tmp) / 'app'
            (app / 'dist/assets').mkdir(parents=True)
            (app / 'dist-electron').mkdir()
            (app / 'dist/assets/index-abc.js').write_text(BUNDLE, encoding='utf-8')
            (app / 'dist/index.html').write_text(
                '<title>Cleanly</title>', encoding='utf-8')
            (app / 'package.json').write_text(
                '{\"name\": \"cleanly\", \"productName\": \"Cleanly\"}',
                encoding='utf-8')
            out = Path(tmp) / 'out'
            debrand.debrand(app, out)
            html = (out / 'dist/index.html').read_text(encoding='utf-8')
            manifest = (out / 'package.json').read_text(encoding='utf-8')
            self.assertIn('<title>Sa6i Clean</title>', html)
            self.assertIn('"productName": "Sa6i Clean"', manifest)
            self.assertIn('"name": "sa6i-clean"', manifest)
            self.assertEqual(debrand.leftovers(out), [])

    def test_leftovers_catches_a_lowercase_name(self):
        with TemporaryDirectory() as tmp:
            app = Path(tmp) / 'app'
            (app / 'dist/assets').mkdir(parents=True)
            (app / 'dist-electron').mkdir()
            (app / 'dist/assets/index-abc.js').write_text(BUNDLE, encoding='utf-8')
            (app / 'dist-electron/main.js').write_text('ok', encoding='utf-8')
            (app / 'note.txt').write_text('children:`cleanly`', encoding='utf-8')
            problems = debrand.leftovers(app)
            self.assertTrue(problems)


if __name__ == '__main__':
    unittest.main()
