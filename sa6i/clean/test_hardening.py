"""Tests for the cache-root guard patches. Synthetic text only; nothing runs."""
import hashlib
from pathlib import Path
import tempfile
import unittest

import harden_candidate
import harden_cleaner
import harden_upstream


class UpstreamPatchTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.path = Path(self.work.name) / 'trash.ts'
        self.path.write_bytes((
            "import { promises as fsp } from 'node:fs';\n"
            "import path from 'node:path';\n"
            "const isWin = process.platform === 'win32';\n"
            "const isMac = process.platform === 'darwin';\n"
            "type UnlinkResult = 'ok' | 'gone' | 'locked' | 'denied';\n"
            "\n"
            "export async function deleteCacheEntry(target: string, root: string): Promise<void> {\n"
            "  const out: DeleteOutcome = { freed: 0, removed: 0, locked: 0, denied: 0, refused: false };\n"
            "  try {\n"
            "    await fsp.lstat(target);\n"
            "  }\n"
            "}\n").encode('utf-8'))

    def tearDown(self):
        self.work.cleanup()

    def test_guard_and_helper_are_inserted_with_lf(self):
        harden_upstream.patch_trash(self.path)
        data = self.path.read_bytes()
        self.assertNotIn(b'\r\n', data)
        text = data.decode('utf-8')
        self.assertIn('isUnredirectedRoot', text)
        self.assertIn('if (!(await isUnredirectedRoot(root)))', text)
        self.assertLess(text.index('isUnredirectedRoot'), text.index('deleteCacheEntry(target'))

    def test_patching_twice_is_refused(self):
        harden_upstream.patch_trash(self.path)
        with self.assertRaises(ValueError):
            harden_upstream.patch_trash(self.path)

    def test_unexpected_layout_is_refused(self):
        self.path.write_text('export const nothing = 1;\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            harden_upstream.patch_trash(self.path)


class BundlePatchTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.path = Path(self.work.name) / 'main.js'
        self.path.write_bytes((
            "var x=1;" + harden_cleaner.FUNC + "let t={freed:0};"
            + harden_cleaner.FUNC_BODY + "return t}").encode('utf-8'))

    def tearDown(self):
        self.work.cleanup()

    def test_guard_is_inserted_once_and_keeps_lf(self):
        harden_cleaner.patch_main(self.path)
        data = self.path.read_bytes()
        self.assertNotIn(b'\r\n', data)
        text = data.decode('utf-8')
        self.assertEqual(text.count('Sa6iUnredirectedRoot'), 2)  # definition + call
        self.assertIn("try{if(!await Sa6iUnredirectedRoot(i))return t.refused=!0,t;", text)

    def test_missing_anchor_is_refused(self):
        self.path.write_text('var unrelated=1;\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            harden_cleaner.patch_main(self.path)

    def test_guard_cannot_be_applied_twice(self):
        harden_cleaner.patch_main(self.path)
        with self.assertRaises(ValueError):
            harden_cleaner.patch_main(self.path)

    def test_snippet_hash_is_pinned(self):
        self.assertEqual(hashlib.sha256((harden_cleaner.helper_snippet() + '\n').encode()).hexdigest(),
                         harden_cleaner.SNIPPET_SHA)


class CandidateAssemblyTests(unittest.TestCase):
    def test_only_the_top_level_folder_is_renamed(self):
        name = harden_candidate.entry_name(harden_candidate.OLD_ROOT + 'Sa6i Clean/app.asar')
        self.assertEqual(name, harden_candidate.NEW_ROOT + 'Sa6i Clean/app.asar')
        self.assertEqual(harden_candidate.entry_name('other/file'), 'other/file')

    def test_digests_are_replaced_in_place_and_counted(self):
        old_exe = bytes.fromhex(harden_candidate.OLD_EXE_SHA)
        old_asar = bytes.fromhex(harden_candidate.OLD_ASAR_SHA)
        data = b'prefix' + old_exe + b'middle' + old_asar + b'suffix'
        patched = harden_candidate.patch_desktop(data)
        self.assertEqual(len(patched), len(data))
        self.assertEqual(sum(1 for a, b in zip(data, patched) if a != b), 64)
        self.assertIn(bytes.fromhex(harden_candidate.NEW_EXE_SHA), patched)
        self.assertIn(bytes.fromhex(harden_candidate.NEW_ASAR_SHA), patched)
        self.assertNotIn(old_exe, patched)
        self.assertNotIn(old_asar, patched)

    def test_ambiguous_digest_is_refused(self):
        data = bytes.fromhex(harden_candidate.OLD_EXE_SHA) * 2
        with self.assertRaises(ValueError):
            harden_candidate.patch_desktop(data)


if __name__ == '__main__':
    unittest.main()
