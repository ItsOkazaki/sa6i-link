#!/usr/bin/env python3
"""Build `docs/pitch/deck.html` from `docs/pitch/deck.src.html`.

The deck has to survive a laptop with no network, no Node and no PowerPoint: it is
one HTML file, opened from the repository folder. That means the brand font and the
mark have to be *inside* it rather than next to it, and doing that by hand is how a
300 KB base64 blob ends up pasted into a file people are supposed to edit.

So: the source stays readable, this script inlines the two assets, and `--check`
fails if the built file is stale — the same shape as `cargo xtask tokens --check`,
for the same reason.

    python3 scripts/build-deck.py            # write docs/pitch/deck.html
    python3 scripts/build-deck.py --check    # exit 1 if it is out of date
"""

from __future__ import annotations

import base64
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs/pitch/deck.src.html"
OUTPUT = ROOT / "docs/pitch/deck.html"
MARK = ROOT / "assets/brand/sa6i-mark.svg"

# Only what the deck actually uses: the UI face and the mono face. The bold weight is
# synthesised by the browser, which is fine at presentation sizes and saves 100 KB.
FONTS = [
    ("Figtree", ROOT / "assets/fonts/Figtree.ttf", "100 900"),
    ("Space Mono", ROOT / "assets/fonts/SpaceMono-Regular.ttf", "400"),
]


def font_face(family: str, path: pathlib.Path, weight: str) -> str:
    if not path.exists():
        raise SystemExit(f"missing font: {path}")
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        "@font-face{"
        f'font-family:"{family}";'
        f"font-weight:{weight};"
        "font-style:normal;"
        f'src:url(data:font/ttf;base64,{payload}) format("truetype");'
        "font-display:swap}"
    )


def build() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    if "/*@@FONTS@@*/" not in source:
        raise SystemExit("deck.src.html lost its /*@@FONTS@@*/ placeholder")
    if "@@MARK@@" not in source:
        raise SystemExit("deck.src.html lost its @@MARK@@ placeholder")

    fonts = "\n".join(font_face(*font) for font in FONTS)
    mark = MARK.read_text(encoding="utf-8").strip()

    built = source.replace("/*@@FONTS@@*/", fonts).replace("@@MARK@@", mark)
    # A note in the output, so nobody edits the generated file by accident.
    built = built.replace(
        "<!doctype html>",
        "<!doctype html>\n<!-- GENERATED from deck.src.html by scripts/build-deck.py."
        " Edit the source, not this file. -->",
        1,
    )
    return built


def main() -> int:
    built = build()
    if "--check" in sys.argv[1:]:
        if not OUTPUT.exists():
            print(f"{OUTPUT.relative_to(ROOT)} is missing; run scripts/build-deck.py")
            return 1
        if OUTPUT.read_text(encoding="utf-8") != built:
            print(f"{OUTPUT.relative_to(ROOT)} is out of date; run scripts/build-deck.py")
            return 1
        print(f"{OUTPUT.relative_to(ROOT)} is current")
        return 0

    OUTPUT.write_text(built, encoding="utf-8")
    size = OUTPUT.stat().st_size
    slides = built.count('class="slide"')
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {slides} slides, {size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
