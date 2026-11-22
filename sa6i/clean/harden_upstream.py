#!/usr/bin/env python3
"""Apply the Sa6i cache-root guard to a copy of the pinned Cleanly source.

Upstream `deleteCacheEntry` validates the file it deletes but not the folder it
lives in, so a cache root reached through a junction/symlink is followed. The
guard canonicalises the root once per process and refuses when the real path
differs from the requested one, which makes such cleaning skip instead of
deleting through the redirect.

This script patches a COPY of upstream source for tests and for reproducing the
packaged bundle. It never runs the cleaner and never touches an installation.
The same guard text is applied to the packaged minified bundle by
`harden_cleaner.py`; `verify_upstream_equivalence.py` checks the two agree.
"""
import argparse
import hashlib
import shutil
from pathlib import Path

SOURCE_TRASH_SHA = '28a2f68426ec7511fcbd0e20ce96763dd3042770d8ef314975d5e93b6cde2252'
PATCHED_TRASH_SHA = 'f24e1c0be3fc1766c599df796cff4eeead57c0dd50102c236842021f706156ac'

HELPER = '''
/** Cache roots already checked in this process, keyed by lower-cased path. */
const sa6iRootChecks = new Map<string, boolean>();

/**
 * A cache root reached through a junction or symlink is not the folder this code
 * believes it is: its contents would be deleted through the redirect. Compare
 * the real path with the requested one; Windows and macOS are case-insensitive,
 * and an unresolvable root is refused. Refusing only skips cleaning.
 */
export async function isUnredirectedRoot(root: string): Promise<boolean> {
  const key = path.resolve(root).replace(/[\\/]+$/, '');
  const cached = sa6iRootChecks.get(key.toLowerCase());
  if (cached !== undefined) return cached;
  let ok = false;
  try {
    const real = (await fsp.realpath(root)).replace(/[\\/]+$/, '');
    ok = isWin || isMac ? real.toLowerCase() === key.toLowerCase() : real === key;
  } catch {
    ok = false;
  }
  sa6iRootChecks.set(key.toLowerCase(), ok);
  return ok;
}
'''

ANCHOR = "type UnlinkResult = 'ok' | 'gone' | 'locked' | 'denied';"
GUARD_ANCHOR = '  const out: DeleteOutcome = { freed: 0, removed: 0, locked: 0, denied: 0, refused: false };\n'
GUARD = GUARD_ANCHOR + '''  // Never delete through a junction or symlink above the cache root.
  if (!(await isUnredirectedRoot(root))) {
    out.refused = true;
    return out;
  }
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def patch_trash(path):
    path = Path(path)
    text = path.read_text(encoding='utf-8')
    if HELPER.strip() in text:
        raise ValueError('Guard already applied')
    if text.count(ANCHOR) != 1 or text.count(GUARD_ANCHOR) != 1:
        raise ValueError('Unexpected upstream source layout')
    text = text.replace(ANCHOR, ANCHOR + '\n' + HELPER.strip('\n'), 1)
    text = text.replace(GUARD_ANCHOR, GUARD, 1)
    # Force LF: Windows text mode would write CRLF and change the pinned hash.
    path.write_text(text, encoding='utf-8', newline='\n')


def harden(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    if sha(source / 'electron/services/trash.ts') != SOURCE_TRASH_SHA:
        raise ValueError('Source does not match the reviewed Cleanly v0.2.0 tree')
    shutil.copytree(source, output)
    patch_trash(output / 'electron/services/trash.ts')
    return sha(output / 'electron/services/trash.ts')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    digest = harden(args.source, args.output)
    print(f'Patched source tree: {args.output}')
    print(f'electron/services/trash.ts SHA-256: {digest}')
    if PATCHED_TRASH_SHA != 'PENDING' and digest != PATCHED_TRASH_SHA:
        raise SystemExit('Patched source does not match the pinned hardened hash')


if __name__ == '__main__':
    main()
