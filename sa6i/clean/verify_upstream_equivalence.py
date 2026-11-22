#!/usr/bin/env python3
"""Check that Sa6i Clean's packaged files are a reproducible build of Cleanly 0.2.0.

Cleanly publishes source for the v0.2.0 release (commit b62bef4), but the Sa6i
Link candidate ships a packaged app. This script rebuilds the candidate's
JavaScript from that source plus the documented Sa6i branding patches and
compares every file byte for byte.

It never executes the cleaner or Electron. It reads a source checkout, its
built `dist/` and `dist-electron/` folders, and an already-extracted ASAR.
Running the builds requires the source checkout's own dependencies
(`npm ci --ignore-scripts`) and network access to install them.

Usage:
  python3 sa6i/clean/verify_upstream_equivalence.py SOURCE EXTRACTED_ASAR \\
      [--build] [--source-sha b62bef4d4478cd8d570dcdc537eaddb61ae53eeb]

Exit status 0 means every packaged file was reproduced, with the two
documented metadata exceptions reported. Non-zero means a difference exists.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_candidate import replace_exact  # noqa: E402
from prepare_integrated_ui import FRAMELESS_OPTIONS, THEME_OVERLAY, WINDOW_OPTIONS  # noqa: E402
from prepare_theme import apply_to_extracted  # noqa: E402
from prepare_themed_fixture import NEW_DEFAULT, OLD_DEFAULT  # noqa: E402

SOURCE_COMMIT = 'b62bef4d4478cd8d570dcdc537eaddb61ae53eeb'
SOURCE_FILES = {
    'package.json': '2f7821518fe0a0344c8ad7c52e6564e93c7f54c31471ab3f0513ab0cde5a0d5c',
    'electron/services/trash.ts': '28a2f68426ec7511fcbd0e20ce96763dd3042770d8ef314975d5e93b6cde2252',
    'electron/services/walk.ts': 'ec40101e574b4746129f440ba330cbd5a38a5b509bb58938d24a26667d63da62',
}
RENDERER_BUNDLE = 'dist/assets/index-BwXp8TnN.js'
# The packaged build was pruned after bundling and has one blank line added by
# the packaging step; those two files are checked by content instead of hash.
HASH_EXCEPTIONS = {'package.json', 'dist/index.html'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_source(source):
    for name, expected in SOURCE_FILES.items():
        path = source / name
        if not path.is_file():
            raise SystemExit(f'Missing {name}; is this the Cleanly checkout?')
        if sha(path) != expected:
            raise SystemExit(f'{name} does not match the reviewed source; refusing to compare')


def build_source(source):
    """Run the project's own production builds without packaging the app."""
    if not (source / 'node_modules').is_dir():
        raise SystemExit('node_modules is missing; run npm ci --ignore-scripts in the source first')
    for command in (['npx', 'vite', 'build'], ['node', 'scripts/build-electron.mjs']):
        result = subprocess.run(command, cwd=source)
        if result.returncode != 0:
            raise SystemExit(f'Source build failed: {" ".join(command)}')


def expected_tree(source, work):
    """Apply only the documented Sa6i patches to the upstream build outputs."""
    shutil.copytree(source / 'dist', work / 'dist')
    shutil.copytree(source / 'dist-electron', work / 'dist-electron')
    package = json.loads((source / 'package.json').read_text(encoding='utf-8'))
    package['name'] = 'sa6i-clean'
    package['productName'] = 'Sa6i Clean'
    (work / 'package.json').write_text(json.dumps(package, indent=2) + '\n', encoding='utf-8')

    replace_exact(work / 'dist/index.html', '<title>Cleanly</title>', '<title>Sa6i Clean</title>', 1)
    apply_to_extracted(work)  # Sa6i theme stylesheet, fonts and license texts

    main = work / 'dist-electron/main.js'
    replace_exact(main, 'title:"Cleanly",titleBarStyle', 'title:"Sa6i Clean",titleBarStyle', 1)
    replace_exact(main, WINDOW_OPTIONS, FRAMELESS_OPTIONS, 1)
    replace_exact(main, THEME_OVERLAY, 'void 0', 1)
    replace_exact(main, OLD_DEFAULT, NEW_DEFAULT, 1)

    ui = work / RENDERER_BUNDLE
    for before, after, count in [
        ('children:`cleanly`', 'children:`Sa6i Clean`', 2),
        ('sub:`Make Cleanly feel like yours.', 'sub:`Make Sa6i Clean feel like yours.', 1),
        ('children:`Cleanly does not replace your antivirus.', 'children:`Sa6i Clean does not replace your antivirus.', 1),
        ('sub:`Caches, temp files and logs your apps rebuild on their own. Safe items are picked for you.`',
         'sub:`Warning: cleanup can permanently delete selected files, including Recycle Bin contents. '
         'Review selections and back up first.`', 1),
        ('Caches and temp files are deleted for good — they rebuild themselves. '
         'Your own files always go to Trash.',
         'Cleanup can permanently delete files. Review selections and back up anything important first.', 1),
        ('title:`Send feedback`', 'title:`Send feedback to the original Cleanly developer`', 1),
        ('title:`Support Cleanly`', 'title:`Support Cleanly (original developer)`', 2),
        ('function Ee({size:e=30}){return(0,F.jsxs)(`svg`,{className:`brand-mark`,width:e,height:e,'
         'viewBox:`0 0 32 32`,"aria-hidden":`true`,children:[(0,F.jsx)(`path`,{d:`M16 2c1.2 7.4 6.6 12.8 '
         '14 14-7.4 1.2-12.8 6.6-14 14-1.2-7.4-6.6-12.8-14-14C9.4 14.8 14.8 9.4 16 2z`,fill:`url(#g-brand)`}),'
         '(0,F.jsx)(`circle`,{cx:`25`,cy:`7`,r:`2.4`,fill:`#ffb547`})]})}',
         'function Ee({size:e=30}){return(0,F.jsx)(`img`,{className:`brand-mark`,width:e,height:e,'
         'src:`./assets/sa6i-clean.png`,alt:``})}', 1),
    ]:
        replace_exact(ui, before, after, count)
    shutil.copyfile(Path(__file__).resolve().parent / 'assets/icon-128.png',
                    work / 'dist/assets/sa6i-clean.png')


def check_metadata(actual_package, expected_package):
    """The packaged manifest is pruned; the fields that drive loading must match."""
    for key in ('name', 'productName', 'version', 'main', 'type'):
        if actual_package.get(key) != expected_package.get(key):
            return f'package.json {key}: {actual_package.get(key)!r} != {expected_package.get(key)!r}'
    return None


def check_index_html(actual, expected):
    """The packaging step left one extra blank line; nothing else may differ."""
    strip = lambda text: [line for line in text.splitlines() if line.strip()]  # noqa: E731
    if strip(actual) != strip(expected):
        return 'dist/index.html content differs beyond a blank line'
    if actual.count('\n') - expected.count('\n') not in (0, 1):
        return 'dist/index.html blank-line count differs unexpectedly'
    return None


def compare(expected, actual):
    files = lambda root: {str(p.relative_to(root)): p for p in root.rglob('*') if p.is_file()}  # noqa: E731
    want, have = files(expected), files(actual)
    problems = []
    for name in sorted(set(want) | set(have)):
        if name not in want:
            problems.append(f'unexpected packaged file: {name}')
        elif name not in have:
            problems.append(f'missing packaged file: {name}')
        elif name in HASH_EXCEPTIONS:
            continue
        elif sha(want[name]) != sha(have[name]):
            problems.append(f'content differs: {name}')
    if 'package.json' in have:
        message = check_metadata(json.loads(have['package.json'].read_text(encoding='utf-8')),
                                 json.loads(want['package.json'].read_text(encoding='utf-8')))
        if message:
            problems.append(message)
    if 'dist/index.html' in have:
        message = check_index_html(have['dist/index.html'].read_text(encoding='utf-8'),
                                   want['dist/index.html'].read_text(encoding='utf-8'))
        if message:
            problems.append(message)
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', type=Path, help='Cleanly v0.2.0 source checkout')
    parser.add_argument('asar_dir', type=Path, help='extracted resources/app.asar of the candidate')
    parser.add_argument('--build', action='store_true', help='run the source builds before comparing')
    parser.add_argument('--source-sha', default=SOURCE_COMMIT,
                        help='expected source commit (printed for the provenance record)')
    args = parser.parse_args()
    source, asar = args.source.resolve(), args.asar_dir.resolve()
    if not asar.is_dir():
        raise SystemExit('The ASAR directory does not exist')
    check_source(source)
    print(f'Source: Cleanly v0.2.0, commit {args.source_sha}')
    print(f'Packaged ASAR: {asar}')
    if args.build:
        build_source(source)
    with tempfile.TemporaryDirectory(prefix='sa6i-equivalence-') as tmp:
        expected = Path(tmp) / 'app'
        expected.mkdir()
        expected_tree(source, expected)
        problems = compare(expected, asar)
        rebuilt = {name: sha(expected / name) for name in
                   ('dist-electron/main.js', 'dist-electron/preload.cjs', RENDERER_BUNDLE)}
    for name, digest in rebuilt.items():
        print(f'Rebuilt {name}: {digest}')
    if problems:
        print('\nNOT EQUIVALENT:')
        for problem in problems:
            print(f'- {problem}')
        return 1
    print('\nEvery packaged file matches the source build plus the documented Sa6i patches.')
    print('Accepted metadata deviations: pruned package.json fields and one blank line in dist/index.html.')
    print('This is build provenance only; it is not a safety, licensing or Windows compatibility verdict.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
