#!/usr/bin/env python3
"""Remove the original developer's tip and feedback screens from the cleaner.

The cleaner is the packaged Cleanly build, so its renderer bundle still carries
a Support/Tip tab and a Feedback tab, both of which open pages and addresses
belonging to its original author. This script edits an already-extracted app
directory (`resources/app` of the packaged app) and leaves the cleanup code
untouched: it only removes those two navigation entries and rewrites the brand
words around them.

The removal is structural, not a fixed-string match: it finds the nav entry by
its className and cuts the whole JSX call that contains it, so it survives the
whitespace and variable-name differences between builds. Every edit is counted
and an unexpected layout raises instead of writing a half-edited bundle.
"""
import argparse
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
NAV_MARKERS = ('className:`nav-item${e===`support`?` on`:``}`',
               'className:`nav-item${e===`feedback`?` on`:``}`')
OPENERS = ('(0,F.jsxs)(`button`', '(0,F.jsx)(`button`')


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


def rewrite_only(text):
    """Brand and outbound-address rewrite, without removing any entry."""
    counts = {}
    for before, after in OUTBOUND:
        counts[before] = text.count(before)
        text = text.replace(before, after)
    counts[BRAND_FROM] = text.count(BRAND_FROM)
    return text.replace(BRAND_FROM, BRAND_TO), counts


def debrand_text(text):
    """Apply every edit to one bundle, returning (new_text, counts)."""
    counts = {}
    for marker in NAV_MARKERS:
        text = remove_element(text, marker)
        counts[marker] = 1
    for before, after in OUTBOUND:
        counts[before] = text.count(before)
        text = text.replace(before, after)
    counts[BRAND_FROM] = text.count(BRAND_FROM)
    text = text.replace(BRAND_FROM, BRAND_TO)
    return text, counts


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


def debrand(app, output):
    app, output = Path(app).resolve(), Path(output).absolute()
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    shutil.copytree(app, output)
    total = {}
    for bundle in bundles(output):
        text = bundle.read_text(encoding='utf-8')
        if NAV_MARKERS[0] not in text or NAV_MARKERS[1] not in text:
            # Only the renderer carries the navigation; every other bundle is
            # still rewritten, but no entry is removed from it.
            new, counts = rewrite_only(text)
            if new != text:
                bundle.write_text(new, encoding='utf-8', newline='\n')
                total[str(bundle.relative_to(output))] = counts
            continue
        new, counts = debrand_text(text)
        bundle.write_text(new, encoding='utf-8', newline='\n')
        total[str(bundle.relative_to(output))] = counts
    return total


def leftovers(app):
    """Anything that still names the original author's screens or pages."""
    problems = []
    for bundle in bundles(app):
        text = bundle.read_text(encoding='utf-8')
        for pattern in (r'Cleanly', r'beyond-media', r'beyond-apps',
                        r'Send feedback to the original'):
            if re.search(pattern, text):
                problems.append(f'{bundle.name}: {pattern}')
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
