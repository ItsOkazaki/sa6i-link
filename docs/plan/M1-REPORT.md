# M1 report — telemetry, evidence, rules

The first four slices of the intelligence core: measure a machine, prove what
was measured, turn it into findings that carry their own evidence, keep the
result long enough to say "for three weeks" instead of "right now", and write
down the machines the rules must be right about. No UI yet, no model, no
actions.

## What exists now

| Piece | Where | State |
| --- | --- | --- |
| The machine model | `core/sa6i-link-intel/src/model.rs` | **done** — `MetricState`, `Snapshot`, CPU/memory/volumes/uptime |
| Findings and evidence | `core/sa6i-link-intel/src/findings.rs` | **done** — severity, confidence, evidence, rendering |
| The rule engine | `core/sa6i-link-intel/src/rules.rs` | **done** — 3 rules, hysteresis, stable ordering |
| Sample history | `core/sa6i-link-intel/src/store.rs` | **done** — bounded ring, `held_for` windows |
| Windows collectors | `core/sa6i-link-intel-win/src/lib.rs` | **done** — CPU (total and per-core), memory, volumes, uptime, heaviest processes, no admin |
| Durable history | `core/sa6i-link-intel/src/history.rs` | **done** — SQLite, 1 row/min, findings as upserts, retention |
| Golden scenarios | `core/sa6i-link-intel/tests/` | **done** — 8 recipe fixtures, firing case and near-miss per rule |
| Privacy, as a test | `core/sa6i-link-intel/tests/privacy.rs` | **done** — neither intel crate can reach a socket-capable crate |
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

## Slice 3 — golden scenarios

A rule is a claim about a machine, and a claim is only as good as the case that
disproves it. `core/sa6i-link-intel/tests/scenarios/*.json` holds eight written
machines: each file is the input *and* the expected answer, side by side, so a
reviewer checks the numbers against the sentence next to them.

The files are recipes, not 600 hand-written snapshots — a segment says "eleven
minutes at 95 % full" and the harness expands it to the 1 Hz series the
collector would have produced. That keeps a scenario readable and reviewable,
which a 200 KB wall of JSON is not.

| Scenario | What it pins |
| --- | --- |
| `01-disk-full-for-eleven-minutes` | fires: Warning, subject `C:` |
| `02-disk-cleared-before-the-window` | eight minutes full then three minutes clean → silent |
| `03-disk-ninety-eight-is-critical` | the 97 % escalation is real, not aspirational |
| `04-disk-network-and-unreadable` | a network share and an unreadable volume produce nothing |
| `05-memory-tight-for-three-minutes` | fires: Notice |
| `06-memory-dipped-inside-the-window` | a dip inside the two-minute window disqualifies the claim |
| `07-uptime-twenty-days` | fires: Info |
| `08-uptime-one-hour` | silent |

Three tests enforce the harness rather than the other way round:

- `every_scenario_produces_exactly_the_findings_it_promises` — the finding set
  must match **exactly**, in both directions, and every finding that appears
  must carry evidence.
- `every_rule_has_a_firing_case_and_a_near_miss` — iterates `RULES` and fails if
  any rule has no scenario proving it fires, or none proving it can stay quiet.
  Adding a rule without fixtures breaks the build instead of shipping a guess.
- `a_severity_word_is_never_invented_by_a_scenario` — a typo like `"warning"`
  would otherwise make an expectation unreachable and the test would pass for
  the wrong reason.

There is also `the_json_a_page_receives_has_the_field_names_it_expects`: the
snapshot's JSON keys and the `Unknown` encoding (`{"state":"unknown","value":
"not_collected_yet"}`) are asserted, because renaming a field is a breaking
change for the Monitor page that no compiler would catch.

## Slice 4 — per-core CPU

The first M1.1 collector. `CpuSample` gains `per_core: Vec<MetricState<f32>>`,
and the Win32 collector fills it from
`NtQuerySystemInformation(SystemProcessorPerformanceInformation)`.

Three decisions:

**The maths is the maths that was already tested.** The per-core counters are
idle/kernel/user, exactly the shape `CpuTimes` has had since slice 1, so
`percent_busy_since` — with its clamping, its backwards-counter rule and its
zero-interval rule — is reused per core rather than reimplemented. Only the
plumbing is new, and `core_states` is a pure function with its own tests: the
first sample is `Unknown(NotSampledYet)` per core; a core that appears later is
`Unknown` too; one backwards counter makes *that* core unknown and leaves the
others alone.

**No struct layout from memory.** `SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION` is
not in the `windows` crate, and declaring forty-eight bytes of layout because I
remember them is how a collector starts reporting nonsense. The buffer is read
as six `u64` words per processor instead — idle, kernel, user are the first
three — and the allocation is `Vec<u64>` so it is 8-byte aligned for the kernel's
stores. Every field I use is in the first 24 bytes, where the three
`LARGE_INTEGER`s unmistakably are.

**A group is not a machine.** Windows answers this class per *processor group*,
and the call returns the caller's group. On a machine with more than 64 logical
processors, `per_core` is short. It says so: the length is the number measured,
the CLI prints "N measured" rather than "N cores", and the architecture doc
records the deviation. The alternative — the undocumented `Ex` class — is a
guessing game with a struct layout, and it can wait until there is a 128-core
machine to check it against.

The CLI gained one line:

```text
  cpu        41.7 %
  cores      8 measured, 2 above half, busiest 96.4 %
```

## The compile blocker slice 1 left behind

Reading the crate against the workspace lints found one: `unsafe_code = "deny"`
is inherited by `sa6i-link-intel-win` through `[lints] workspace = true`, and the
crate is *made* of `unsafe` Win32 calls, so it could not have compiled. Every
function that calls a C API now carries its own `#[allow(unsafe_code)]` — the
pattern `sa6i-link-core` already uses — with the crate docs stating the rule:
this crate is the only place the allow exists, and it is granted per function,
not per crate.

That is the value of the audit: nothing in the sandbox could compile it, and
CI would have gone red on a technicality that took ten seconds to fix once it
was seen.

## Slice 5 — the promises, as tests

Two of M1's exit criteria are properties of the code rather than of a run:
"nothing leaves the machine" and the layering rules in
`docs/architecture/MODULE-MAP.md` §1. Both are now read out of `Cargo.lock` by
`core/sa6i-link-intel/tests/privacy.rs` instead of being asserted in prose.

**The socket check.** Every crate reachable from `sa6i-link-intel` *and* from
`sa6i-link-intel-win` is compared against a list of crates that can open a
socket or a TLS session. Today both closures are clean (62 and 74 crates). The
list is a ratchet, not a proof against every name the ecosystem will invent —
so adding a network stack to a core crate now requires editing the list, which
is exactly the visible, deliberate act it should be.

**The layering check.** The same closure proves `sa6i-link-intel` is the bottom
of the stack: no `sa6i-link-core`, no protocol, no `windows`, no CLI.

Three details make the test trustworthy rather than decorative:

- It builds the graph **by name**, ignoring versions. A check that cannot name
  a version has to keep every candidate edge; dropping one because the lock
  spelled `"log"` instead of `"log 0.4.29"` is how such a test passes while a
  network crate is linked.
- The pieces that must be present (`serde`, `tracing`, `rusqlite`) are asserted
  before the absence check, so a parser that silently stopped parsing fails
  loudly instead of passing vacuously.
- The parser itself is tested on a miniature lock that includes a versioned
  edge, in the real format.

## Where M1 stands against its exit criteria

M1 exits when these hold. The plan's wording, and what would demonstrate it:

| Exit criterion | Demonstrated by | State |
| --- | --- | --- |
| Numbers within ±3 % of Task Manager | a side-by-side run on a real machine | **needs your PC** |
| 1 Hz for 30 min under budget | `--samples 1800` with a stopwatch and a CPU reading | **needs your PC** |
| Win7 renders `Unsupported`, with reasons | the `cfg(not(windows))` collector and the reason strings already do this on any non-Windows build; a real Win7 pass is still owed | **partly demonstrable** |
| CLI JSON stable and tested | `tests/scenarios.rs`: field names, `Unknown` encoding, exact finding sets | **done** |
| No admin prompt anywhere | no elevation API is called and no manifest requests it; the collectors use `GetDiskFreeSpaceExW`, `GlobalMemoryStatusEx`, `GetSystemTimes`, `NtQuerySystemInformation` — all available to a standard user | **done by construction, needs a click-through** |
| Nothing leaves the machine | `tests/privacy.rs`: no socket-capable crate in either intel closure | **done** |

Two of six need a machine, one needs an old one, and the Monitor page (M1.3) is
not started. Which means M2's rules should wait for the two-machine run rather
than stack more rules on numbers nobody has compared.

## Slice 6 — the heaviest processes

`Snapshot.processes` carries the eight heaviest processes by working set, with
pid and executable name. This is the answer to "what is using my RAM", which is
the question the Monitor page gets asked most.

**Memory first, because memory is instantaneous.** Working set is a fact about
one moment; CPU per process is a rate, and a rate needs two samples keyed by
something that survives a pid being reused — which means pid *and* creation
time, a map that outlives a snapshot, and a rule about what to show when a
process appears mid-interval. That is a slice of its own, and pretending
otherwise would put a number on a page that means something different from what
it says.

**The sort is in the core, not the collector.** `top_processes` is a pure
function on `Vec<ProcessSample>`: heaviest first, ties broken by pid so the list
is identical across runs and a screenshot can be compared with a log, shorter
lists cut to the limit, and a process whose memory could not be read sorted last
rather than pretending to be 0 B. Three tests, no machine needed.

**A process it cannot open is absent, not zero.** Every open uses
`PROCESS_QUERY_LIMITED_INFORMATION` — no elevation, ever — which is also why
`System` and other users' sessions are simply not on the list. The alternative
is a row called "System" with 0 MB next to it, which is a worse lie than an
absence.

One detail worth recording: the return value of `EnumProcesses` is deliberately
ignored (`let _status = …`) because the count of bytes written is what says
whether the call worked. That also means the collector does not care whether
this crate models the call as `BOOL` or `Result<()>` — a distinction I could not
settle from documentation, and one that would otherwise have been a guess
compiled into the code.

## What the collectors do not do, on purpose

Per-core CPU, disk throughput, GPU memory and per-process detail are **not** in
this slice. Each needs either a heavier API (`PdhAddEnglishCounter`), a
version-gated one (`QueryVideoMemoryInfo` is Windows 10+), or a different
question (a process snapshot is not a counter). Adding them without fixtures
would be guessing with a UI attached. Temperatures stay unavailable: that needs
a driver, and Stage B settled that we report the reason instead.

Evaluated but not shipped: `GetPerformanceInfo` for a process count (easy, but
nothing yet uses it) and `GetVolumeInformationW` for filesystem names (only
useful once the UI shows them).

Disk throughput and GPU memory are still open — see `## Next` — and per-process
CPU is deliberately absent from slice 6 for the reason given there. They were
left out rather than bundled so that a machine reporting bad per-core numbers
cannot also be a machine whose PDH query is suspect.

## Verification

| Claim | Method |
| --- | --- |
| Type-level honesty | `MetricState` has no `Deref`, no `Default`-to-zero, and every accessor is fallible |
| Window arithmetic | Fixture stores built at 1 Hz; `held_for` tested for too-short history, a disqualifying sample, and pruning |
| Rule thresholds | Firing case and near-miss case per rule, including "network drive ignored", "worst volume wins", "unreadable volume is silent" |
| CPU maths | Tick deltas including an idle machine, a backwards counter, and a kernel/idle disagreement |
| Ordering | Worst-first, and identical ids across two evaluations of the same store |
| Scenario fixtures | Every scenario was re-derived by an independent implementation (Python, written from the documented thresholds and windows, not from the Rust) — 8/8 agree with the expectations, so the fixtures are right for a reason other than "the code produced them" |
| SQL semantics | The exact statements (schema, upsert, ordering, retention cutoffs, the `MAX`-on-empty → `NULL` path) were replayed against a real SQLite in Python — 17/17 checks pass, so the assumptions the Rust makes are SQLite's actual behaviour, not my memory of it |
| Dependency graph | Both intel closures were recomputed independently in Python from the same lock — 62 and 74 crates, zero network-capable, which is what the Rust test asserts |
| Win32 surface (slice 4) | The module path, signature and class constant of `NtQuerySystemInformation` were checked against the `windows` 0.62.2 API listing rather than recalled; the per-processor struct is deliberately *not* declared, so only the first three of its six words are read |
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

0. **Stop and compile.** Six commits of Win32 calls, SQLite calls and a new
   dependency have never been through `rustc`. Until they have, every further
   collector is written on top of assumptions nobody has checked, and the cost
   of finding out grows with each one:

   ```powershell
   cargo fmt --all
   cargo test --locked -p sa6i-link-intel -p sa6i-link-intel-win
   cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- --json
   ```

1. **M1.1, the rest:** disk throughput (PDH, English counters) and GPU memory.
   Each gets its own slice and its own fixture, for the same reason slice 4 was
   one collector and not four. Per-process CPU joins them once there is a
   two-sample map keyed by pid and creation time.
   - PDH is deliberately not written yet. The `windows` crate is not in this
     sandbox, and I could not confirm from documentation whether
     `PdhOpenQueryW` returns `WIN32_ERROR` or `PDH_STATUS` in 0.62 — two
     plausible signatures, and one of them is a compile error in a crate that
     cannot be compiled here. Guessing that is worse than waiting for one
     `cargo check`.
   - GPU memory needs a decision before code: `QueryVideoMemoryInfo` answers for
     *the calling process* on an adapter, not for the machine, so using it as
     "GPU memory pressure" would be a true number answering the wrong question.
     The documented machine-wide source is the PDH counter set
     `\GPU Adapter Memory(*)\Dedicated Usage` (Win10 1709+), which means GPU
     waits for the PDH work rather than racing it.
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
