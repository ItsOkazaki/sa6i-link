# Dead code, scanned by shrink-anything

[shrink-anything](https://github.com/EL4CTEO/shrink-anything) finds code nothing
calls, files nothing names, dependencies nothing uses and assets nothing shows, then
deletes them — keeping each cut only if your own tests still pass.

This repository cannot satisfy that condition. The intel crates have never been
compiled, so no cut could be *proved* by anything; a deletion here would be a guess
dressed as a measurement. So what was run is `scan`, which changes nothing, and this
page is the result with the triage that follows from it. **Nothing was deleted.**

## What was run

```sh
npm install -g @el4cteo/shrink-anything@0.1.0
shrink-anything -C . scan --all --json
```

Version 0.1.0, the `linux-x64` build, from npm on 2026-11-16.

One wrinkle worth recording, because it is the difference between a claim and a
reproduction. The published binary needs glibc 2.39; the sandbox this repository is
written in has 2.36. It links exactly two symbols from 2.39 — `pidfd_spawnp` and
`pidfd_getpid`, both **weak**, both from Rust's process spawning — so a fifteen-line
stub library that provides those two names under a `GLIBC_2.39` version script is
enough to start it:

```sh
LD_PRELOAD=/tmp/glibc-shim.so shrink-anything -C . scan --all --json
```

The stubs return `ENOSYS`. That is honest for `scan`, which spawns nothing; it would
not be honest for `cut`, which runs a check — and `cut` is not what this page is.
`docs/audit` records the fact rather than the incantation: on any machine with a
current glibc, and on the Ubuntu runner in
[`.github/workflows/shrink-scan.yml`](../../.github/workflows/shrink-scan.yml), the
plain command works.

## What it read

| | |
| --- | --- |
| files | 576 — Rust 266, Kotlin 147, Python 78, C 30, JavaScript 20, C++ 15 |
| lines | 302,625 (265,920 of code) |
| dependencies | 111 |
| assets | 82 files, 35.1 MB |
| for an agent to read | ≈3.1 M tokens |

## What it found

66 candidates and 47 groups of duplicate code.

| kind | tier "safe" | tier "needs a look" |
| --- | --- | --- |
| code | 7 | 40 |
| file | 4 | 14 |
| dependency | 1 | — |

The tool is explicit about how it decides: *"it counts names instead of building a
call graph. A count can only miss dead code, never invent it."* That is true of the
counting and not true of the conclusion, which is why every row below was checked by
hand before being repeated here.

## The triage

Six candidates, checked with `grep` in this tree. The verdict column is the part the
tool cannot supply.

| candidate | the tool's reason | what I found | verdict |
| --- | --- | --- | --- |
| `desktop/app/i18n/sa6i-link_de.ts`, `_zh_CN.ts`, `_tr.ts` — 31,031 lines | "no other file mentions sa6i-link_de" | `desktop/app/src/i18n.rs:182` builds the name: `format!("sa6i-link_{code}.ts")`, and `LANGUAGES` names `de`, `zh_CN`, `tr` | **not dead.** A filename assembled at runtime is invisible to a text scan. Keep all three. |
| `Sa6iLinkNode` — 1,201 lines, `core/sa6i-link-ffi/src/lib.rs:3269` | "all 6 mentions are its own definition, but it is exported from a library" | it is `#[derive(uniffi::Object)]`, the crate's only such object; no `.rs`, `.kt` or `.qml` outside the crate names it, and none of the 147 Kotlin files mentions uniffi at all | **undecided, and the only serious one.** UniFFI bindings are generated at build time, so a consumer could exist outside this repository. The crate is 4,799 lines with no in-tree caller: either the bindings live elsewhere and this file should say so, or the surface is dead. A decision, not a delete. |
| `retry_all_failed_queue_items` — 59 lines, `core/sa6i-link-core/src/node.rs:2318` | "all 5 mentions are its own definition, but it is a public member" | `node.rs` → `store.rs` → the FFI wrapper at `core/sa6i-link-ffi/src/lib.rs:3594`, which is itself unreachable in-tree | **dead at the top of a chain.** No single cut proves it; a second scan after the first would. |
| `try_start_watcher` — 47 lines, `desktop/app/src/win/ble_beacon.rs:160` | "its only mention is its own definition" | the doc comment above line 104 says the RSSI watcher "stays off: phones don't broadcast" — the function is kept for a feature that was switched off | **not dead, but not used.** Delete it, or mark it `#[allow(dead_code)]` with the reason it is still there. Leaving it unnamed is the worst of the three. |
| `timelineDayLabel` — 11 lines, `android/…/HomeScreen.kt:3385` | "its only mention is its own definition" | one hit in the whole repository, its own definition | **likely dead Kotlin**, and provable only by the Android build — no Kotlin compiles here. |
| `sa6i-vcam` — 1 dependency, `desktop/app/Cargo.toml:30` | "nothing imports or runs it" | `desktop/vcam` exists as a workspace crate; nothing in `desktop/app/src` names `sa6i_vcam`; `linux/vcam.rs` only writes module config paths | **likely unused**, and cheap to prove with `cargo build -p sa6i-link-desktop` once that is possible. |

Two more things the scan reports that are deliberate:

- **`sa6i/baseline/windows-arabic-v8/source/`** — 33 files, two 10,306-line Arabic
  catalogues and 14 patch scripts, none of them named anywhere the scan read. It is
  the archived source of the shipped v8 Windows test build, and it documents itself:
  `READ-ME-FIRST.txt` beside it gives the provenance, the EXE's SHA-256, what each
  file is, and that it is a private binary patch of 0.1.5 rather than a source build.
  Keep it. The first version of this page said the folder was undocumented, which was
  an assumption about a directory I had not opened; the file that contradicts it is
  the first one in the listing.
- **47 duplicate groups, 11,054 lines and 3.3 MB.** The largest is
  `desktop/app/i18n/sa6i-link_ar.ts` against its baseline copy — deliberate. The
  interesting one is `sample_m4a` in `core/sa6i-link-cli/src/main.rs:4677` against
  `test_m4a` in `desktop/app/src/recordings.rs:1272`: 181 near-identical lines in two
  crates, which is the shape of test-helper code that was copied once and then
  diverged.

## Cross-checked with two other tools

One name-counting tool is a witness, not a verdict. Two more were run, chosen
because they decide differently.

**vulture 2.16** — Python, scope analysis rather than name counting, installed from
PyPI and run here:

```sh
vulture . --min-confidence 60 --exclude "node_modules,third_party,.git,target"
```

Fifteen items, and the interesting part is the overlap.
`sa6i/clean/debrand_cleaner.py:154` holds an unused function `bundles` —
shrink-anything reached the same line by asking "does any *text* mention this name",
vulture by asking "is it reachable in its own scope". Two methods, one answer, and
the same line: that is worth more than either tool alone.

It also found dead code in the two scripts written in this session, which is the
least comfortable and most useful result of the day:

| file | what | what happened |
| --- | --- | --- |
| `scripts/check-fixtures.py` | `MEMORY_TOTAL` and `COMMIT_LIMIT` declared, never read | removed. The simulator speaks in percentages, the way the fixtures do; the totals never entered an answer |
| `scripts/fixtures-report.py` | a `by_name` helper nothing called | removed |

Both files are clean at 60 % confidence now, and both still pass: `check-fixtures.py`
reported the same 34 fixtures and 25 thresholds afterwards, and
`fixtures-report.py --check` said the generated page was still current — which is
what proves the helper was dead rather than merely unused.

The other twelve items are mostly test scaffolding, and 60 % confidence means "looks
dead", not "is dead": `handle_starttag` in `sa6i/tests/test_landing_page.py:16` is an
`HTMLParser` override called by the parser, and the `*Harness` and `*Policy` classes
in `sa6i/clean/test_*.py` are mixins reached by inheritance. The four real ones are in
`sa6i/clean/delivery/transplant_icon.py`: three tuple targets unpacked and never used
at line 126, one at line 67. They are left for whoever next touches that script,
because it runs against the Electron bundle and this sandbox has no bundle to run it
against — a fix nobody can execute is a guess with a diff.

**cargo-machete 0.10.1** — Rust, reads the manifests and greps the crates' sources:
the answer to "is `sa6i-vcam` really unused", which shrink-anything raised and could
not settle. Its prebuilt release is served from `release-assets.githubusercontent.com`,
which this sandbox cannot reach, so it ran in CI instead. It found **six** unused
dependencies across four manifests, exit code 1:

| crate | unused | checked |
| --- | --- | --- |
| `desktop/app` | `anyhow`, `sa6i-vcam` | 0 mentions of either in `src/` |
| `core/sa6i-link-intel-win` | `serde`, `tracing` | the crate uses `serde_json` only; 0 mentions of `tracing` |
| `core/sa6i-link-adb` | `tracing` | 0 mentions |
| `third_party/iroh-mdns-address-lookup` | `derive_more` | not ours: vendored code, left alone by convention |

So the `sa6i-vcam` finding was real, and two tools that decide by different rules —
name counting across the tree, manifest against source — agreed on the same crate.
That is the strongest result of the three runs, and the reason to keep both.

**None of them were removed.** `cargo machete --fix` is one command, and so is the
build that would prove the workspace still compiles without them; this sandbox has
neither, and deleting a dependency nobody can rebuild is the same mistake as deleting
code nobody can test. The five that belong to this project are named above so the
first person with a toolchain can run `--fix`, `cargo test --locked`, and watch the
workspace shrink by five manifest lines and whatever they were pulling in.

### Where the CI outputs land

Artifacts are the evidence, and this sandbox cannot download them: the artifact URL is
a signed `blob.core.windows.net` link, and the release host earlier in this page is
blocked too. So a manual run — or any change to the workflow file — also writes the
three outputs into one rolling issue, [`#18 Dead code scan`][issue]. The weekly
schedule does not, because a scanner that mails people is a scanner people mute.

[issue]: https://github.com/ItsOkazaki/sa6i-link/issues/18

The first CI run reproduced vulture's list minus the three items fixed above, which is
what makes the fixes checkable rather than claimed: the lists agree line for line.

## What this does not license

- **No cut.** The tool's own rule is that a cut stays only if your check exits 0 and
  at least as many tests run as before. There is no check here that can run, so
  there is no cut that could be justified. `.github/workflows/shrink-scan.yml` runs
  this scan plus the two below, weekly, and says in its summary that nothing was
  deleted.
- **No "the repository is 11 % smaller" claim.** The 32,693 lines in the "can go"
  bucket include the three translation catalogues and the archived baseline. After
  triage the honest number is far smaller and not yet known.

## When the gate closes

The order, and only this order:

```sh
cargo test --locked -p sa6i-link-intel     # the check must pass before it proves anything
shrink-anything -C . cut --only code -- cargo test --locked -p sa6i-link-intel
shrink-anything -C . report                # before and after, for the pull request
shrink-anything -C . undo --all            # byte for byte, if the result is not wanted
```

`--only code` on the first run: the file and dependency candidates are the ones
whose consumers this repository cannot see (translations by format string, bindings
by code generation), so they go last and by hand.
