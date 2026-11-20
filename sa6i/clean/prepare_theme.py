#!/usr/bin/env python3
"""Apply the draft Sa6i Link skin to an extracted experimental cleaner.

This helper does not change the executable integrity hash, repackage the ASAR,
change native host pins, or synchronize the host's selected theme. Its output
is therefore not launchable as the pinned integration fixture yet. It must not
be applied to the user's existing installation.
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'sa6i/clean/assets'
FONTS = ROOT / 'assets/fonts'
OLD_LINK = '  <link rel="stylesheet" crossorigin href="./assets/index-Dv7r3g2E.css">'
NEW_LINK = OLD_LINK + '\n  <link rel="stylesheet" href="./assets/sa6i-integrated-theme.css">'


def apply_to_extracted(app):
    app = Path(app)
    index = app / 'dist/index.html'
    text = index.read_text(encoding='utf-8')
    if text.count(OLD_LINK) != 1 or 'sa6i-integrated-theme.css' in text:
        raise ValueError('Unexpected or already themed cleaner renderer')
    assets = app / 'dist/assets'
    copies = [
        (ASSETS / 'integrated-theme.css', assets / 'sa6i-integrated-theme.css'),
        (FONTS / 'Figtree.ttf', assets / 'sa6i-figtree.ttf'),
        (FONTS / 'SpaceMono-Regular.ttf', assets / 'sa6i-space-mono.ttf'),
        (FONTS / 'OFL-Figtree.txt', assets / 'sa6i-figtree-license.txt'),
        (FONTS / 'OFL-SpaceMono.txt', assets / 'sa6i-space-mono-license.txt'),
    ]
    if any(not src.is_file() or dst.exists() for src, dst in copies):
        raise ValueError('Missing source asset or unexpected destination asset')
    for source, destination in copies:
        shutil.copyfile(source, destination)
    index.write_text(text.replace(OLD_LINK, NEW_LINK), encoding='utf-8')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extracted_asar', type=Path)
    args = parser.parse_args()
    apply_to_extracted(args.extracted_asar)
    print('Applied draft skin to extracted fixture only; rebuild integrity pins before launch.')
