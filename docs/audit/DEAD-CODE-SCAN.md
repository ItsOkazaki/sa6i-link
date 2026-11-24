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

## What this does not license

- **No cut.** The tool's own rule is that a cut stays only if your check exits 0 and
  at least as many tests run as before. There is no check here that can run, so
  there is no cut that could be justified. `.github/workflows/shrink-scan.yml` runs
  the same scan weekly and says so in its summary.
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
