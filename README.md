# Sa6i Link

Sa6i Link connects an Android phone to a computer for pairing, screen mirroring and device control. This is an experimental test build.

## Download

The [Windows test package](https://github.com/ItsOkazaki/sa6i-link/releases/tag/sa6i-windows-arabic-v8-test) contains an app folder, not an installer. **A startup error has been reported** on some systems; see the release notes before testing. Keep your previous working version and back up shared preferences and pairings.

To select Arabic, open **Settings → General → Language → More → العربية**.

## Status

The current package and source changes need device testing. Arabic needs human review, full right-to-left layout is unfinished, and performance presets are not included. On Android 11, the test app is intended to follow the phone's system language; in-app language selection remains unresolved. See [test status](sa6i/STATUS.md).

The Windows test is a binary/resource patch, not a source-built release.

## The intelligence core

Sa6i Link also has an in-house diagnostics core: a Rust crate that measures the
machine, runs rules over the measurements, and only reports a finding when it can
show the evidence that produced it. It is written, simulated against fixtures, and
**not yet compiled** — the milestone documents say which parts are which.

- [Presentation and judge Q&A](docs/pitch/PRESENTATION-AND-QA.md) — the words: the
  30-second and 5-minute pitches, the demo script, and 55 questions with answers.
- [The slides](docs/pitch/deck.html) — one self-contained page; open it in a browser
  and press `→`. Built from `deck.src.html` by `python3 scripts/build-deck.py`.
- [How the core is built](docs/architecture/INTELLIGENCE-CORE.md) and
  [the rule plan](docs/plan/M2-RULES.md).
