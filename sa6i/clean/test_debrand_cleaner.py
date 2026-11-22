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


if __name__ == '__main__':
    unittest.main()
