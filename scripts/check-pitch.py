#!/usr/bin/env python3
"""Check that the numbers in the pitch still match the repository.

    python3 scripts/check-pitch.py

The pitch says twelve rules, thirty-four fixtures, twenty-five thresholds, twelve
TOML files. Those numbers move every time a rule ships, and a slide that says
eleven after the twelfth rule landed is the exact failure this project exists to
avoid - a confident sentence about something nobody re-checked.

`build-deck.py --check` proves the deck matches its source. This proves the source
matches the code, which is the other half: the two files cannot agree with each
other and both be wrong.

Counts are recounted from the repository rather than typed in, so this file does
not need editing when a rule ships - only fixed when the pitch needs it.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INTEL = ROOT / "core/sa6i-link-intel"

# What is scanned: the words that face a judge or a new reader.
PITCHED = [
    ROOT / "README.md",
    ROOT / "docs/pitch/PRESENTATION-AND-QA.md",
    ROOT / "docs/pitch/deck.src.html",
]

WORDS = {
    word: number
    for number, word in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()
    )
}

COUNT = r"(\d+|" + "|".join(WORDS) + r")"


def counted(text):
    """`12`, `twelve` and `Twelve` all mean twelve."""
    lowered = text.lower()
    return WORDS[lowered] if lowered in WORDS else int(text)


# Each claim: how it reads in prose, and how the repository answers it.
CLAIMS = [
    (
        "rules",
        re.compile(rf"\b{COUNT}\s+rules\b", re.IGNORECASE),
        lambda: len(re.findall(r"Rule \{ def: \w+, evaluate: \w+ \}", (INTEL / "src/rules.rs").read_text())),
        "registry entries in src/rules.rs",
    ),
    (
        "TOML files",
        re.compile(rf"\b{COUNT}\s+TOML files\b", re.IGNORECASE),
        lambda: len(list((INTEL / "rules").glob("*.toml"))),
        "*.toml in rules/",
    ),
    (
        "fixtures",
        re.compile(rf"\b{COUNT}\s+fixtures\b", re.IGNORECASE),
        lambda: len(list((INTEL / "tests/scenarios").glob("*.json"))),
        "*.json in tests/scenarios/",
    ),
    (
        "thresholds",
        re.compile(rf"\b{COUNT}\s+(?:compiled\s+)?thresholds\b", re.IGNORECASE),
        lambda: len(
            re.findall(
                r"pub \w+: \w+,",
                (INTEL / "src/rules.rs").read_text().split("pub struct Thresholds")[1].split("\n}")[0],
            )
        ),
        "fields in Thresholds",
    ),
]


def scan():
    """Every claim the pitch makes, with where it was made."""
    found = []
    for path in PITCHED:
        if not path.exists():
            print(f"missing pitched file: {path.relative_to(ROOT)}", file=sys.stderr)
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            for name, pattern, truth, source in CLAIMS:
                for match in pattern.finditer(line):
                    # "a fixture claimed by two rules" and "cannot start with zero
                    # rules" are about how many rules a *file* may name, not about
                    # how many rules exist. The distinction is the whole point of
                    # this check, so it is written down rather than pattern-guessed.
                    before = line[: match.start()].rstrip()
                    if before.endswith(("by", "with", "between", "than")):
                        continue
                    try:
                        value = counted(match.group(1))
                    except ValueError:
                        continue
                    found.append((path, number, name, value, truth, source, line.strip()))
                    break
    return found


def main():
    claims = scan()
    if not claims:
        print("no counts found in the pitch; the patterns are stale, not the pitch", file=sys.stderr)
        return 1

    failures = 0
    checked = 0
    truth_by_name = {}
    for _, _, name, _, truth, source, _ in claims:
        if name not in truth_by_name:
            truth_by_name[name] = (truth(), source)

    for path, number, name, value, _, _, line in claims:
        expected, source = truth_by_name[name]
        checked += 1
        if value != expected:
            failures += 1
            where = f"{path.relative_to(ROOT)}:{number}"
            print(f"FAIL {where}: says {value} {name}, the repository has {expected} ({source})")
            print(f"       {line[:120]}")

    for name, (expected, source) in sorted(truth_by_name.items()):
        print(f"{expected:>3} {name} ({source})")
    if failures:
        print(f"{failures} of {checked} counts disagree with the repository")
        return 1
    print(f"all {checked} counts in the pitch match the repository")
    return 0


if __name__ == "__main__":
    sys.exit(main())
