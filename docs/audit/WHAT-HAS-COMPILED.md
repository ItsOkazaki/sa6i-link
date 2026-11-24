# What has actually been compiled

Every page in this repository separates what was measured from what was asserted, and
the line that mattered most was this: **nothing here had ever been compiled.** That
line is now narrower, and this page is where the evidence for the narrower version
lives. If a claim elsewhere says something builds, the proof has to be here or it is
still an assertion.

## The evidence

| | |
| --- | --- |
| Workflow | `.github/workflows/rust-check.yml` |
| Runners | `ubuntu-latest`, `windows-latest` |
| Command | `cargo check --locked --all-targets --keep-going` and `cargo test --locked --no-fail-fast` |
| Crates | `sa6i-link-protocol`, `sa6i-link-core`, `sa6i-link-ffi`, `sa6i-link-cli`, `sa6i-link-adb`, `sa6i-link-intel`, `sa6i-link-intel-win`, `xtask` |
| Result | `EXIT:check:0 EXIT:test:0 EXIT:clippy:0` on both runners |
| Tests | 472 passed, 0 failed, 6 ignored (Ubuntu); 471 passed, 0 failed, 6 ignored (Windows) |
| Where to read it | issues [#20](https://github.com/ItsOkazaki/sa6i-link/issues/20) and [#21](https://github.com/ItsOkazaki/sa6i-link/issues/21) |

The six ignored tests are the scale benchmarks, which only run under `--ignored`
because they write multi-gigabyte files and hold a stopwatch to it. One target on
Windows reports one test fewer than on Linux: it is platform-conditional by design.

## What this proves

The platform-free half of the core compiles and its tests pass. The `#[cfg(windows)]`
half — the PDH counter code, the WMI-free process list, the volume enumeration — is
also compiled, on a Windows runner, which a Linux build never sees. Both halves type
check; neither has ever run against a Windows 7 machine.

## The nine defects it found

Seven were real. They are listed because the point of a build is what it catches, not
that it went green.

| Where | What |
| --- | --- |
| `intel/rules_file.rs` | `Refusal::BadDuration` was pushed and matched by two tests, and never declared |
| `intel/model.rs` | a `Snapshot` initialiser set every field except `gpu` |
| `intel/history.rs` | the `finding` insert named eight columns and supplied seven values: **history had never stored a finding** |
| `intel-win/pdh.rs` | `number()` lived outside `mod imp`, reading PDH types that do not exist there |
| `intel-win/lib.rs` | `GetSystemTimes` imported from the wrong module; `GetLogicalDriveStringsW` called with the pre-0.59 two-argument signature; one `MetricState<Bytes>` reused for an `f32` |
| `cli/main.rs` | `--power`'s type had no `Clone`, no `ValueEnum` and no `Display`, so the parser could not be built |
| `core/clip_kind.rs` | a test still expected the repository's old owner, `thtbee` |

Two more were tests asserting something other than what they measured: the budget test
looked for `OVER` on the cpu line when the collection line is the one that says it, and
a 4 ms run costing 1 ms of CPU — a quarter of a core — was asked to pass.

## What it does not prove, and no run of it will

- **The app.** `desktop/app` needs Qt 6.12 and cxx-qt, and `spikes/s1-qt-rust` needs
  them too. Neither is in this workflow. `ci.yml` builds them on `windows-latest`,
  `macos-latest` and `ubuntu-latest` — and has never run on this branch, because it
  triggers on `main` and on pull requests, not on branch pushes. **The window has
  never been built.**
- **QML, the installer, NSIS, the ARM64 cross build, the Android targets.** Untouched.
- **Windows 7.** `windows-latest` is Windows Server 2022. PDH counters, `cldapi.dll`,
  the missing VxKex shims — none of that is exercised by compiling. The rule that says
  what the core does when a counter is absent is tested against synthetic snapshots.
- **Any rule against a real machine.** The fixture harness feeds JSON; no collector has
  been asked a question by a rule on hardware.
- **`SA6I Clean`.** Still never executed anywhere.

## Lints and formatting, which were turned on and then satisfied

`ci.yml` gates on `cargo fmt --all --check` and `cargo clippy -- -D warnings`, so this
workflow does too. Both were red when they were first pointed at this source, and both
were fixed by their own output rather than by opinion:

- **Formatting.** Nothing had ever formatted this workspace. The workflow now runs
  `cargo fmt --all` and commits rustfmt's answer to the branch — 41 files the first
  time. rustfmt is the only thing here that decides what "formatted" means.
- **Lints.** Eleven diagnostics, nine of them in this workspace's own code:
  `collapsible_if` ×5 (edition 2024's let-chains), `assertions_on_constants` ×2 (now
  `const _: () = assert!(..)`, checked at compile time instead of at run time),
  `needless_bool`, `chunks_exact_to_as_chunks`, and one `#[must_use]` `NTSTATUS` that
  was being dropped.

Three of the six unused dependencies cargo-machete found are gone, which is only
allowed now that something can rebuild: `tracing` from `sa6i-link-adb`, `serde` and
`tracing` from `sa6i-link-intel-win`. The lockfile's three edges went with them, and
the run after that change is the proof they were unused — `check:0 test:0` again.
`anyhow` and `sa6i-vcam` stay: they live behind Qt, and this workflow does not build Qt.

## The app, through ci.yml, on pull request #22

The draft pull request finally pointed `ci.yml` at this code. What it said, before the
fixes above:

| Job | Where it stopped |
| --- | --- |
| Core (ubuntu-latest) | `Format` |
| Core (windows-latest), Windows app (x64) checks, macOS app, Linux app (x64) | `Clippy` |
| Windows app (x64) | `Release build` |
| Windows app (ARM64 cross build) | `Build and Package` |
| Android app | `Unit tests and debug build` |
| Licenses and dependencies | `License headers` — eight files in `sa6i/clean` with no SPDX line |

That the Windows app job reached `Clippy` at all means Qt 6.12 installed and the app
crate got as far as being linted; `Release build` is a separate job and its failure is
not yet explained by anything readable from here. Every pull-request run since then has
sat at `action_required` and needs a human to approve it in the GitHub UI.
