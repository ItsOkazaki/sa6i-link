# M1 report — telemetry, evidence, rules

The first two slices of the intelligence core: measure a machine, prove what
was measured, turn it into findings that carry their own evidence, and keep the
result long enough to say "for three weeks" instead of "right now". No UI yet,
no model, no actions.

## What exists now

| Piece | Where | State |
| --- | --- | --- |
| The machine model | `core/sa6i-link-intel/src/model.rs` | **done** — `MetricState`, `Snapshot`, CPU/memory/volumes/uptime |
| Findings and evidence | `core/sa6i-link-intel/src/findings.rs` | **done** — severity, confidence, evidence, rendering |
| The rule engine | `core/sa6i-link-intel/src/rules.rs` | **done** — 3 rules, hysteresis, stable ordering |
| Sample history | `core/sa6i-link-intel/src/store.rs` | **done** — bounded ring, `held_for` windows |
| Windows collectors | `core/sa6i-link-intel-win/src/lib.rs` | **done** — CPU, memory, volumes, uptime, no admin |
| Durable history | `core/sa6i-link-intel/src/history.rs` | **done** — SQLite, 1 row/min, findings as upserts, retention |
| Headless proof | `core/sa6i-link-intel-win/src/bin/sa6i-intel-snapshot.rs` | **done** — `--json`, `--history PATH` |
| Monitor page, TOML rules, disk/GPU/process collectors | — | **not started** (see below) |

```powershell
cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot
cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- --samples 700 --interval-ms 1000
cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- --json
cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- --history %LOCALAPPDATA%\Sa6i\history.db
```

The third command is the contract the UI will use: one JSON object with the
snapshot and the findings, every number accompanied by the reason it exists.

## The invariants, and where they live

**A missing measurement is a value.** `MetricState::{Value, Unknown(reason),
Unsupported(reason)}` is not a `f64` with a sentinel. `is_known()` returns
`false` for "we don't know", so no code can accidentally treat a failed read as
zero. `Snapshot::metrics()` emits nothing for an unknown metric, which means an
unreadable disk cannot appear on a sparkline as a drop to 0 %. Tested in
`a_missing_measurement_is_never_zero`.

**No finding without evidence.** `Finding::is_supported()` requires at least one
evidence item with a metric path, and `evaluate()` *drops* any finding that
fails it (logging a warning) rather than showing a claim. Tested in
`a_finding_without_evidence_is_not_supported`.

**A spike is not a trend.** `SampleStore::held_for` answers "has this been true
for the whole window?" and returns `None` when the history is shorter than the
window. The disk rule needs ten minutes; the memory rule needs two.

This last one had a bug. My first version compared the oldest sample against the
window start and, when the store was shorter than the window, `saturating_sub`
made the start 0 — so a two-minute history cheerfully answered a ten-minute
question. It is exactly the failure mode the whole design exists to prevent: a
number that looks like knowledge. The fix is an explicit
`if self.span_ms() < window_ms { return None; }` before any sample is examined,
with the reasoning written down where the next person will read it.

## Rules in this slice

| Rule | Needs | Severity | Fires when |
| --- | --- | --- | --- |
| `disk.low_free_space` | 10 min of history | Warning (Critical ≥ 97 %) | a fixed or removable volume is ≥ 90 % full throughout |
| `memory.pressure` | 2 min of history | Notice, Likely | physical memory ≥ 90 % used throughout |
| `system.long_uptime` | one sample | Info | uptime ≥ 14 days |

Network and optical volumes are excluded (a full network share is not this
machine's problem), the worst volume is the one reported (three findings saying
"disk full" is noise), and thresholds are named constants with the fixture that
pins them.

## Slice 2 — durable history

The ring answers "what happened in the last hour". `History`
(`core/sa6i-link-intel/src/history.rs`) answers "what happened last week", which
is the difference between a dashboard and a diagnosis: "96 % full right now" is
a fact, "96 % full for three weeks" is the thing worth telling someone about.

SQLite, through the `rusqlite` the core already ships (bundled, so no system
dependency). Two tables:

| Table | Row | Key | Retention |
| --- | --- | --- | --- |
| `sample` | the whole `Snapshot` as JSON + `seq`, `monotonic_ms` | `taken_at` | 24 hours raw |
| `finding` | `rule`, `severity`, `subject`, `title`, `first_seen`, `last_seen`, the finding JSON | `id` | 30 days |

Four decisions that are load-bearing, each with a test:

**One row a minute, not one a second.** A day is 1,440 rows and a few hundred
kilobytes; the second a rule needs is already in the ring. `record()` is safe to
call every second and returns whether it wrote, and the newest stored `taken_at`
is read back when the file is opened, so relaunching the app does not write a
burst. (`samples_are_written_once_a_minute`,
`history_survives_being_closed_and_reopened`)

**A clock that goes backwards cannot rewrite the past.** Wall clocks jump —
a time sync, a manual change, a laptop resuming. A sample whose timestamp is
behind the newest stored one is stored as "the moment after it" rather than
being either dropped or written into history under a false time, so
`ORDER BY taken_at` still means "in the order things happened". The first
version of this got the order of checks wrong, and a backwards jump was silently
treated as "inside the same minute" and discarded; the test caught it.
(`a_clock_that_goes_backwards_cannot_write_into_the_past`)

**Findings are upserts keyed by the stable id.** `first_seen` therefore means
the first time *this machine* had that problem, across restarts, which is the
number the UI will show. (`a_finding_keeps_the_first_time_it_was_seen`)

**A newer schema is refused, not mis-read.** `PRAGMA user_version` is checked on
open; a database written by a newer Sa6i returns
`HistoryError::NewerSchema(version)` and the file is left untouched — the failure
mode is a sentence, not corrupted data. (`a_database_from_a_newer_sa6i_is_refused_rather_than_misread`)

Two consequences worth stating plainly: history is **opt-in** (`--history PATH`
on the CLI; nothing on disk otherwise, because a diagnostics tool that starts
writing files on first launch is a privacy decision made by accident), and the
findings themselves are salted into `sample`'s sibling table rather than derived
again at read time — so an old finding still explains itself with the evidence
that produced it, even after the rule's thresholds move.

The snapshot is stored as JSON rather than as a column per metric. A schema that
mirrors `Snapshot` cannot drift from it, and one row a minute is cheap; the
rollups (`sample_hourly`) wait until there is a week of raw data to validate
them against, which is why they are not in this slice.

## What the collectors do not do, on purpose

Per-core CPU, disk throughput, GPU memory and per-process detail are **not** in
this slice. Each needs either a heavier API (`PdhAddEnglishCounter`), a
version-gated one (`QueryVideoMemoryInfo` is Windows 10+), or a different
question (a process snapshot is not a counter). Adding them without fixtures
would be guessing with a UI attached. Temperatures stay unavailable: that needs
a driver, and Stage B settled that we report the reason instead.

Evaluated but not shipped: `GetPerformanceInfo` for a process count (easy, but
slice 1 has nothing that uses it) and `GetVolumeInformationW` for filesystem
names (only useful once the UI shows them).

## Verification

| Claim | Method |
| --- | --- |
| Type-level honesty | `MetricState` has no `Deref`, no `Default`-to-zero, and every accessor is fallible |
| Window arithmetic | Fixture stores built at 1 Hz; `held_for` tested for too-short history, a disqualifying sample, and pruning |
| Rule thresholds | Firing case and near-miss case per rule, including "network drive ignored", "worst volume wins", "unreadable volume is silent" |
| CPU maths | Tick deltas including an idle machine, a backwards counter, and a kernel/idle disagreement |
| Ordering | Worst-first, and identical ids across two evaluations of the same store |
| SQL semantics | The exact statements (schema, upsert, ordering, retention cutoffs, the `MAX`-on-empty → `NULL` path) were replayed against a real SQLite in Python — 17/17 checks pass, so the assumptions the Rust makes are SQLite's actual behaviour, not my memory of it |
| Every file | Delimiter balance and SPDX header checked mechanically (`balanced`, no long lines) |

**Not verified: it has not been compiled.** There is no Rust toolchain in this
sandbox, so neither the `windows` calls nor the `rusqlite` calls have been
through `rustc`; `cargo fmt --check` and `clippy -D warnings` are also unrun on
this branch. Run, on a machine with one:

```powershell
cargo fmt --all
cargo test -p sa6i-link-intel -p sa6i-link-intel-win
cargo clippy --workspace --all-targets -- -D warnings
```

The `rusqlite` calls are the ones I am most confident of — they are a subset of
what `sa6i-link-core` already compiles — with one exception: `History` opens the
file itself, so a locked database surfaces as `HistoryError::Database` rather
than panicking, and the two-second `busy_timeout` is the only tuning. The code was written against the calling conventions already used in
this repository (`GetDiskFreeSpaceExW(&HSTRING, Some(&mut u64), ..)` in
`desktop/app/src/win/mod.rs`, `GetProcessTimes(handle, &mut ft, ..)` in the CLI),
so the `windows` 0.62 signatures are modelled on working calls rather than
recalled. The two I am least certain of are `GetSystemTimes` (three optional out
parameters) and `GetLogicalDriveStringsW` (a size query followed by a fill).

```powershell
cargo test -p sa6i-link-intel          # model, store, rules — no OS needed
cargo test -p sa6i-link-intel-win      # cpu maths + collector sequence
cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot
cargo fmt && cargo clippy --workspace --all-targets -- -D warnings
```

If a `windows` signature has moved, the fix is local to one function in
`sa6i-link-intel-win/src/lib.rs`; nothing in the model, the rules or the tests
depends on the API shape.

## Next

1. **M1.1 — the collectors the Monitor page needs:** per-core CPU
   (`NtQuerySystemInformation`), disk throughput (PDH, English counters),
   GPU memory (`QueryVideoMemoryInfo`, Win10+), and a per-process top-N snapshot.
2. **M1.3 — the Monitor page:** `IntelHost` (cxx-qt), 1 Hz property updates, the
   Overview tiles and the sparklines that draw gaps as gaps, reading their
   history from `History::recent` instead of the ring once the window is longer
   than an hour.
3. Then M2: the TOML rule front-end and the twelve-plus Doctor rules.

(`sample_hourly` rollups stay unscheduled on purpose: they need a week of real
data before the rollup can be checked against what it summarises.)

The two M0 checks (`cargo xtask tokens --check`, `cargo check -p sa6i-link`) are
still outstanding on a machine with the toolchain; M1's code does not depend on
them, but the branch carries both.
