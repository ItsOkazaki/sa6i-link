#!/usr/bin/env python3
"""Remove the original developer's tip and feedback screens from the cleaner.

The cleaner is the packaged Cleanly build, so its renderer bundle still carries
a Support/Tip tab and a Feedback tab, both of which open pages and addresses
belonging to its original author, and its own chrome names that author's
product. This script edits an already-extracted app directory
(`resources/app` of the packaged app) and leaves the cleanup code untouched: it
removes those two navigation entries and rewrites the brand words around them.

The removal is structural, not a fixed-string match: it finds the nav entry by
its className and cuts the whole JSX call that contains it, so it survives the
whitespace and variable-name differences between builds. Every edit is counted
and an unexpected layout raises instead of writing a half-edited bundle.

The brand rewrite covers every text file, not only the JavaScript: the product
name in `package.json`, the window title in `index.html`, the sidebar and About
strings (which the app spells in lowercase), the preload bridge name and the
IPC channel prefix, and the logo, which is drawn inline as an SVG sparkle and
is replaced with the Sa6i Clean emblem embedded as a data URI.
"""
import argparse
import base64
import re
import shutil
from pathlib import Path

BRAND_FROM = 'Cleanly'
BRAND_TO = 'Sa6i Clean'
# The tip checkout and the feedback mailbox belong to the original author.
OUTBOUND = (
    ('Payments are handled by Stripe via beyond-media.ai.', 'Payments are handled by Stripe.'),
    ('https://beyond-media.ai/tips?creator=beyond-apps', 'https://invalid.sa6i/tips'),
    ('https://beyond-media.ai/api/tips', 'https://invalid.sa6i/api/tips'),
    ('contact@beyond-media.ai', 'nobody@invalid.sa6i'),
    ('beyond-apps', 'sa6i'),
    # Catch-all: the reserved .invalid-style name never resolves.
    ('beyond-media.ai', 'invalid.sa6i'),
    ('Cleanly feedback: ', 'Sa6i Clean feedback: '),
)
# The product's own chrome spells the name in lowercase, so a capital-only
# rewrite leaves the sidebar, the About panel, the window title and the app
# name branded. Visible strings are rewritten to "Sa6i Clean" first; what is
# left are identifiers, which move together with the files that use them.
EDITS = (
    ('children:`cleanly`', 'children:`Sa6i Clean`'),
    ('t(`cleanly`,', 't(`Sa6i`,'),
    ('<title>Cleanly</title>', '<title>Sa6i Clean</title>'),
    ('"productName": "Cleanly"', '"productName": "Sa6i Clean"'),
    ('"name": "cleanly"', '"name": "sa6i-clean"'),
    ('exposeInMainWorld("cleanly"', 'exposeInMainWorld("sa6i"'),
    ('window.cleanly', 'window.sa6i'),
    ('cleanly:', 'sa6i:'),
    ('cleanly_data', 'sa6i_data'),
    ('app:"cleanly"', 'app:"sa6i"'),
)
NAV_MARKERS = ('className:`nav-item${e===`support`?` on`:``}`',
               'className:`nav-item${e===`feedback`?` on`:``}`')
OPENERS = ('(0,F.jsxs)(`button`', '(0,F.jsx)(`button`')
# The logo is an inline SVG: a four-point sparkle in a gradient with an amber
# dot. Both ends below are exact, so a changed logo raises rather than leaving
# the original mark in place.
BRAND_MARK_START = 'function Ee({size:e=30}){'
BRAND_MARK_END = 'fill:`#ffb547`})]})}'
LOGO = Path(__file__).resolve().with_name('assets') / 'icon-128.png'
TEXT_SUFFIXES = ('.js', '.cjs', '.mjs', '.css', '.html', '.json')


def remove_element(text, marker):
    """Cut the JSX call whose text contains `marker`, once."""
    if text.count(marker) != 1:
        raise ValueError(f'expected one {marker!r}, found {text.count(marker)}')
    index = text.index(marker)
    starts = [text.rfind(opener, 0, index) for opener in OPENERS]
    start = max(starts)
    if start < 0:
        raise ValueError(f'no JSX call opens before {marker!r}')
    # The call is `(0,F.jsxs)(`button`,{...})`: count from the argument's own
    # bracket, not from the call's, so the call's parens do not close it.
    argument = text.rindex('(', start, text.index('`button`', start))
    depth = 0
    end = None
    for position in range(argument, len(text)):
        character = text[position]
        if character in '([{':
            depth += 1
        elif character in ')]}':
            depth -= 1
            if depth == 0:
                end = position + 1
                break
    if end is None:
        raise ValueError(f'unbalanced JSX call at {marker!r}')
    # Take the separator with it, so the list stays valid.
    if text[end:end + 1] == ',':
        end += 1
    elif text[start - 1:start] == ',':
        start -= 1
    return text[:start] + text[end:]


def brand_mark():
    """The replacement logo function: the supplied emblem, embedded."""
    if not LOGO.is_file():
        raise FileNotFoundError(f'missing logo: {LOGO}')
    encoded = base64.b64encode(LOGO.read_bytes()).decode('ascii')
    return ('function Ee({size:e=30}){return(0,F.jsx)(`img`,'
            '{className:`brand-mark`,src:`data:image/png;base64,' + encoded +
            '`,width:e,height:e,alt:``})}')


def replace_brand_mark(text):
    """Swap the original sparkle for the Sa6i Clean emblem, if it is here."""
    start = text.find(BRAND_MARK_START)
    if start < 0:
        return text, 0
    end = text.find(BRAND_MARK_END, start)
    if end < 0:
        raise ValueError('the brand mark is not closed as expected')
    end += len(BRAND_MARK_END)
    return text[:start] + brand_mark() + text[end:], 1


def apply_brand(text, counts):
    """Every brand rewrite that applies to any text file."""
    for before, after in EDITS:
        counts[before] = counts.get(before, 0) + text.count(before)
        text = text.replace(before, after)
    for before, after in OUTBOUND:
        counts[before] = counts.get(before, 0) + text.count(before)
        text = text.replace(before, after)
    counts[BRAND_FROM] = counts.get(BRAND_FROM, 0) + text.count(BRAND_FROM)
    text = text.replace(BRAND_FROM, BRAND_TO)
    text, marks = replace_brand_mark(text)
    counts['brand mark'] = counts.get('brand mark', 0) + marks
    return text


def rewrite_only(text):
    """Brand and outbound-address rewrite, without removing any entry."""
    counts = {}
    return apply_brand(text, counts), counts


def debrand_text(text):
    """Apply every edit to one bundle, returning (new_text, counts)."""
    counts = {}
    for marker in NAV_MARKERS:
        text = remove_element(text, marker)
        counts[marker] = 1
    return apply_brand(text, counts), counts


def bundles(app):
    """The renderer and main-process JavaScript in an extracted app."""
    app = Path(app)
    found = sorted(app.glob('dist/assets/index-*.js'))
    main = app / 'dist-electron/main.js'
    if main.is_file():
        found.append(main)
    if not found:
        raise ValueError('No JavaScript bundle found in the extracted app')
    return found


def text_files(app):
    """Every text file that can carry the brand: scripts, styles, markup, json."""
    return sorted(path for path in Path(app).rglob('*')
                  if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES)


def debrand(app, output):
    app, output = Path(app).resolve(), Path(output).absolute()
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    shutil.copytree(app, output)
    total = {}
    for path in text_files(output):
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if NAV_MARKERS[0] in text and NAV_MARKERS[1] in text:
            # Only the renderer carries the navigation; every other file is
            # still rewritten, but no entry is removed from it.
            new, counts = debrand_text(text)
        else:
            new, counts = rewrite_only(text)
        if new != text:
            path.write_text(new, encoding='utf-8', newline='\n')
            total[str(path.relative_to(output))] = counts
    return total


def leftovers(app):
    """Anything that still names the original author's product or pages."""
    problems = []
    for path in text_files(app):
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        # Amber is an ordinary accent colour in this app, so the logo is
        # tracked by its own path data rather than by its colour.
        for pattern in (r'(?i)cleanly', r'beyond-media', r'beyond-apps',
                        r'Send feedback to the original', r'url\(#g-brand\)',
                        r'M16 2c1\.2 7\.4'):
            if re.search(pattern, text):
                problems.append(f'{path.name}: {pattern}')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('app', type=Path, help='extracted resources/app directory')
    parser.add_argument('output', type=Path, help='new directory to write')
    args = parser.parse_args()
    counts = debrand(args.app, args.output)
    for name, bundle_counts in counts.items():
        print(name, bundle_counts)
    remaining = leftovers(args.output)
    if remaining:
        raise SystemExit('Still present: ' + ', '.join(remaining))
    print('Debranded app written to', args.output)


if __name__ == '__main__':
    main()
