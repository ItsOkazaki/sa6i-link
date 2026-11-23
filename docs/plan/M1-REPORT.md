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
| The rule engine | `core/sa6i-link-intel/src/rules.rs` | **done** — 3 rules, hysteresis, stable ordering, every threshold a value the caller supplies |
| Sample history | `core/sa6i-link-intel/src/store.rs` | **done** — bounded ring, `held_for` windows |
| Windows collectors | `core/sa6i-link-intel-win/src/lib.rs` | **done** — CPU (total and per-core), memory, volumes, uptime, disk throughput, the busiest processes with their CPU rate, no admin |
| Performance counters | `core/sa6i-link-intel-win/src/pdh.rs` | **done** — English `PhysicalDisk` and `GPU Adapter Memory` counters |
| Sampling verdict | `core/sa6i-link-intel/src/budget.rs` | **done** — rate, per-sample cost and CPU share judged against a stated budget, tested with invented timings |
| Report wording | `core/sa6i-link-intel-win/src/report.rs` | **done** — one copy of the sentences, printed by both `sa6i-link intel snapshot` and the standalone binary |
| Window averages | `core/sa6i-link-intel/src/summary.rs` | **done** — mean of what was measured, with the counts; unknown excluded, never averaged in as zero |
| Process CPU | `core/sa6i-link-intel/src/cpu.rs` | **done** — a rate per process, keyed by pid *and* creation stamp, so a recycled pid starts over; 6 tests, no machine needed |
| Monitor data | `core/sa6i-link-intel/src/view.rs` | **done** — tiles, sparklines with gaps, process rows with memory and CPU, volume rows; words chosen here, Qt only places them |
| Monitor page | `desktop/app/src/bridge/intel.rs`, `qml/pages/MonitorPage.qml` | **written, never built** — one sampling thread, one JSON frame a second, Overview (tiles, sparklines) and Detail (cores, volumes, processes, limits); needs a machine with Qt |
| Durable history | `core/sa6i-link-intel/src/history.rs` | **done** — SQLite, 1 row/min, findings as upserts, retention |
| Golden scenarios | `core/sa6i-link-intel/tests/` | **done** — 8 recipe fixtures, firing case and near-miss per rule |
| Verification harness | `scripts/verify-m1.ps1`, `docs/plan/M1-VERIFY.md` | **written, never run** — the six exit criteria in one command, a markdown record, and the two rows that need a human rather than marked green |
| Privacy, as a test | `core/sa6i-link-intel/tests/privacy.rs` | **done** — neither intel crate can reach a socket-capable crate |
| Headless proof | `core/sa6i-link-intel-win/src/bin/sa6i-intel-snapshot.rs` | **done** — `--json`, `--history PATH` |
| TOML rules, Doctor rules, actions | — | **not started** (M2, see below) |

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
| Numbers within ±3 % of Task Manager | `--samples 60 --interval-ms 1000 --average` next to Task Manager's Performance tab | **needs your PC, measurable now** |
| 1 Hz for 30 min under budget | `--samples 1800 --interval-ms 1000 --budget`: prints the rate, the per-sample cost and this process's CPU share, and exits 3 on a miss | **needs your PC, measurable now** |
| Win7 renders `Unsupported`, with reasons | the `cfg(not(windows))` collector and the reason strings already do this on any non-Windows build; a real Win7 pass is still owed | **partly demonstrable** |
| CLI JSON stable and tested | `tests/scenarios.rs`: field names, `Unknown` encoding, exact finding sets; the same payload from `sa6i-link intel snapshot --json` | **done, one payload shared by two front-ends** |
| No admin prompt anywhere | no elevation API is called and no manifest requests it; the collectors use `GetDiskFreeSpaceExW`, `GlobalMemoryStatusEx`, `GetSystemTimes`, `NtQuerySystemInformation` — all available to a standard user | **done by construction, needs a click-through** |
| Nothing leaves the machine | `tests/privacy.rs`: no socket-capable crate in either intel closure | **done** |

Two of six need a machine, one needs an old one, and the Monitor page now exists
with nothing having compiled it. Which means M2's rules should wait for the
two-machine run rather than stack more rules on numbers nobody has compared.

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

## Slice 7 — disk throughput, and how the PDH guess was settled

`Snapshot.disk_io` carries read and write bytes per second, summed over physical
disks — Task Manager's Performance-tab number, and what "the disk is busy" means
to a person.

**The hold-up last slice was real, and it had a real answer.** I would not write
PDH while the return type of `PdhOpenQueryW` was a coin flip — `WIN32_ERROR` or
`PDH_STATUS`, one of which is a compile error. The way out was not a better
guess but the generated documentation, which `microsoft/windows-docs-rs`
publishes per item and which is readable through the GitHub API. Every signature
in `pdh.rs` now comes from there, for `windows` 0.62.2 exactly:

```text
PdhOpenQueryW(PCWSTR, usize, *mut PDH_HQUERY) -> u32
PdhAddEnglishCounterW(PDH_HQUERY, PCWSTR, usize, *mut PDH_HCOUNTER) -> u32
PdhCollectQueryData(PDH_HQUERY) -> u32
PdhGetFormattedCounterValue(PDH_HCOUNTER, PDH_FMT, Option<*mut u32>, *mut PDH_FMT_COUNTERVALUE) -> u32
PDH_HQUERY(pub *mut c_void)   PDH_FMT(pub u32)   PDH_FMT_DOUBLE: PDH_FMT
PDH_FMT_COUNTERVALUE { CStatus: u32, Anonymous: PDH_FMT_COUNTERVALUE_0 }
PDH_FMT_COUNTERVALUE_0 { doubleValue: f64, … }
```

The function returns a plain `u32` — zero is success — which is why the checked
pattern is `!= 0` rather than a typed error. The same source settled
`EnumProcesses(...) -> Result<()>`, so slice 6's `let _status` hedge is gone and
that call is matched properly now.

Three decisions in the collector:

**English counters, not localised ones** (`PdhAddEnglishCounterW`). Counter
display names are translated; asking for `\PhysicalDisk(_Total)\Disk Read
Bytes/sec` on a French Windows finds nothing, and a collector reporting 0 B/s
forever on a French machine is worse than one reporting nothing.

**A rate needs two samples.** The first collection has no interval behind it, so
it reports `Unknown(NotSampledYet)` rather than the 0 PDH would happily hand
back — on a busy disk that 0 is a lie.

**Both statuses are checked.** PDH separates "the call worked" from "the data is
valid" via the counter's own `CStatus`; believing the first without the second is
the exact mistake this crate exists to prevent. Non-finite and negative values
are refused too.

The query is opened once and owned by the collector, so its handle closes in
`Drop` — PDH queries are not reference counted, and a leak would be one kernel
object per second.

## Slice 8 — GPU memory, and the last collector

`Snapshot.gpu` carries the machine's graphics adapters with dedicated VRAM used
and owned. This completes M1.1.

**Why not `QueryVideoMemoryInfo`.** That call — which the plan named — answers
for *the calling process* on one adapter. Presenting it as "GPU memory pressure"
would be a true number answering the wrong question, which is the failure mode
this project is built around. The machine-wide source is the counter set
`\GPU Adapter Memory(*)\Dedicated Usage` (Windows 10 1709+), the same set Task
Manager reads, and slice 7 had already built the query machinery.

**A missing counter set is not a failure of ours.** `GpuCounters::new` maps
`PDH_CSTATUS_NO_OBJECT` and `PDH_INVALID_PATH` to
`Unsupported(NotOnThisWindowsVersion)` and everything else to
`Unknown(CollectorFailed)`. That is how Windows 8.1 — or a driver without WDDM
2.0 GPU counters — gets the honest sentence instead of a broken-collector alarm,
and it is the mechanism by which "Win7 renders Unsupported, with reasons" holds.

**Zero dedicated memory is a fact, not a measurement error.** An integrated GPU
owns no VRAM and reports 0. `GpuAdapter::percent_used()` therefore returns `None`
when the limit is 0 rather than dividing by it, and clamps when a driver reports
more used than exists instead of printing 140 %. Tested, along with the choice
of the heaviest adapter.

Two implementation notes: the instance names (`luid_0x00000000_0x…_phys_0`) are
copied out of PDH's buffer before it drops, and the adapter list is sorted
heaviest-first so a page that shows one shows the discrete GPU rather than the
iGPU.

## Slice 9 — the Monitor's data, before the Monitor

M1.3 is a Qt page, and Qt is the one thing in this repo that has never been
compiled here either. So the part of the page that has an opinion is not Qt:
`core/sa6i-link-intel/src/view.rs` turns a snapshot, the samples before it and
a findings count into four tiles, two sparklines, a core strip, a process table
and a volume list — every string finished, every fraction already between 0
and 1. `MonitorView` is `PartialEq` and tested; `MonitorPage.qml` will only
place things.

The two rules the project rests on are about rendering as much as collecting,
so this is where they are enforced rather than promised:

- **A tile with no reading says why.** `Tile::missing(id, reason)` produces
  `—`, an empty track and the reason sentence. Tested for all four tiles at
  once, because "we handle Unknown" is exactly the claim that decays when only
  one widget is checked.
- **A gap is a gap.** `Sparkline` stores `Option<f32>`, and `normalized` keeps
  the `None`s, so a dropped sample draws a hole instead of a point at the
  bottom of the box. A one-minute window holds 60 points and drops the oldest.

Two things found while writing it, both worth the paragraph:

`Bytes::percent_used` reads its receiver as the bytes *available* and answers
what is used — right for a volume's free space, exactly inverted for a process's
own memory. A 1 GB process on a 16 GB machine would have shown **93.75 %**.
`share_of(part, total)` exists now and a test pins 6.25 %; the wrong answer
looked plausible, which is the reason the test is there.

The disk tile has **no fraction**. CPU, memory and GPU are percentages of a
capacity the machine can name; throughput has no ceiling worth drawing against,
and a bar three-quarters full would be a number the collector never measured.

And one more thing said in the tile rather than hidden: an integrated GPU
reports its memory in use and the note "shared memory; no dedicated VRAM",
because it owns none. There is a value and no percentage, which is the honest
pair for that hardware.

## Slice 10 — the Monitor page

M1.3's surface: a `Monitor` destination in the rail, the command palette and the
title bar, and a page built from four tiles, two minute-long sparklines, the
logical processors, the volumes and the eight heaviest processes.

**The host.** `IntelHost` (`desktop/app/src/bridge/intel.rs`) is a cxx-qt
singleton with one job: run one thread that samples once a second, evaluate the
rules against the ring it keeps (so a finding's window is minutes long even
though a frame is one second), and hand the page a finished `MonitorView` as
JSON. Four properties: the frame, `live`, `samples`, `intervalMs`. The thread
owns the collector because the handles inside it belong to the thread that
opened them, and it sleeps in 50 ms slices so `stop()` is felt immediately
rather than up to a second later.

Two ownership details worth naming, because both are bugs in waiting:

- The run flag is an `Arc<AtomicBool>` **replaced** on every `start()`, not
  reused. A thread still winding down keeps the old flag, which is already
  false, so a quick stop-and-start cannot end with two samplers writing frames.
- The page stops sampling when it is destroyed. The rail is a `Loader`; leaving
  the page tears it down, and a Monitor that samples the machine while nobody
  is looking is exactly the kind of thing this project should not do.

**Why JSON.** `MonitorView` is already the finished frame, and one string
property means one binding to re-evaluate per tick rather than a dozen — and no
cxx-qt struct bridging to get right blind. The cost is a `JSON.parse` a second
over a few kilobytes, which is what several existing pages already do. The wire
format is pinned by a test: `missing` arrives as `"not_sampled_yet"`, `fraction`
as `null`, and a gap in the sparkline as `null` rather than `0`.

**The line is drawn by `Sparkline.qml`, in a `Canvas`, and it breaks at gaps.**
It walks the points, and on a `null` it strokes what it has and starts a new
path, so nothing is drawn across a missing sample. One measured moment is a dot,
because a single point is not a line and nothing at all would look like a
failure of the page.

**What the page does not do:** it has no arithmetic — every string, every `0..1`
fill and every reason sentence is already decided in `view.rs` — and it never
shows `0` for something it did not measure. The tiles show a dash and the reason;
an unmeasured core is an empty bar with a dash above it; a volume with no free
space figure says why.

**Honest state:** this is the only slice in the project that no check here can
touch. There is no Qt and no Rust toolchain in this sandbox, CI builds the app on
a machine that has both, and the things I could not verify are specific: that
`cxx_qt::CxxQtThread<IntelHost>` is the right handle type in 0.10, that
`rust_mut()` projects the run flag the way `history.rs` projects its rows, that a
`#[qml_singleton]` in a new file in `build.rs`'s `files([…])` list is registered
by name, and that the `Canvas` drawing calls I used exist in Qt 6's 2D context.
Everything else — the view, the wire format, the gap rule, the share arithmetic —
is tested.

## Slice 11 — the two machine checks, as commands

Two of M1's six exit criteria need a real PC, and both were written as things a
person does with a stopwatch: compare against Task Manager, and sample for thirty
minutes "under budget" without saying what the budget is. That is a bad way to
hold an exit criterion — it produces an opinion, not a number.

So: two flags on the existing CLI, and the arithmetic behind them in
`core/sa6i-link-intel/src/summary.rs` where it is tested.

**`--average`** prints the window's mean CPU and memory with the counts that make
the mean honest — `cpu 12.4 % (60 of 60 samples) · memory 61.2 % (58 of 60
samples) · over 59 seconds`. Unreadable samples are excluded from the mean and
counted, never averaged in as zero; a machine whose collector failed half the
time would otherwise look idle, which is the same lie the rest of the engine
exists to prevent. `--samples 60 --interval-ms 1000 --average` is the command to
hold next to Task Manager's Performance tab.

**`--budget`** answers the other criterion with three numbers and a verdict:

```text
  budget
    rate       1.00 Hz of 1.00 Hz over 30 minutes — ok
    collection mean 6.2 ms, worst 41.0 ms, ceiling 1000 ms — ok
    cpu        0.31 % of one core, ceiling 1 % — ok
    verdict    PASS
```

The budget is now a definition rather than a feeling: a sample may spend at most
a quarter of its interval collecting, no single sample may overrun the interval,
the achieved rate must stay within 5 % of the requested one, and the whole
process must use under 1 % of one core. A miss exits `3` so the check can gate
something later. The CPU figure comes from `GetProcessTimes` on the process's own
pseudo-handle — kernel plus user time, in 100 ns units — and where it cannot be
read the line says so and does not fail the run, because an unmeasured cost is
not a cheap one.

**What this does not do:** it cannot tell you whether the numbers are *right*.
The ±3 % comparison is still a person looking at two screens; all this does is
make the thing being compared a mean with a sample count instead of a single
twitchy reading. And the timing half measures the Windows collector at 1 Hz,
which is what the plan's thirty minutes are about — not the page, which draws at
whatever rate Qt gives it.

## Slice 12 — `sa6i-link intel snapshot`, and one copy of the words

M1's plan names the surface `sa6i intel snapshot`; the CLI's binary is called
`sa6i-link`, so the command is `sa6i-link intel snapshot`. What existed was only
a separate binary, which is not the same thing: the CLI is what a person or a
script reaches for, and a second binary is a second thing to remember. Adding the
subcommand by copying the first one would have produced two reports that agree
only by luck, so this slice moved the report out of `main()` first.

Three pieces, each in the crate that can test it:

- **`report.rs`** (`sa6i-link-intel-win`) holds every sentence the report is made
  of, as `Vec<String>` rather than `println!`: the caller owns the stream, so
  `--json` stays pure JSON on stdout, and the wording can be checked without a
  terminal. Both front-ends print the same lines in the same order.
- **`budget::Verdict`** (`sa6i-link-intel`) holds the verdict arithmetic that was
  sitting inside the binary's `main`. It is now judged against invented timings
  in six tests — a slow sample, a drifted rate, a greedy process, an unmeasured
  CPU cost, one sample, and an empty run — which is the only way to know a check
  can fail before a machine has to prove it.
- **`sample_window`** (`sa6i-link-intel-win`) is the one sampling loop: 1 Hz,
  sleeping between samples and not after the last, timing only when asked.

**The command runs before the node.** `sa6i-link` starts its network node before
dispatching anything; `Command::Intel` is handled ahead of that, so measuring
this PC needs no identity, no socket and no data directory. That is partly
tidiness and partly the privacy promise: nothing can leave the machine from a
process that never opened a socket.

`sa6i-link intel snapshot` takes `--samples`, `--interval-ms`, `--json`,
`--no-findings`, `--average`, `--budget` and `--history`, behaves exactly like
the standalone binary, and returns `3` when the budget missed.

**Unverified, and it is the usual kind:** the clap wiring and the two
hand-edited dependency entries in `Cargo.lock` (`cargo --locked` will notice
within a second if I got the latter wrong). The arithmetic and the wording are
tested.

## Slice 13 — Overview and Detail

M1's plan says the Monitor has an Overview *and* a Detail; slice 10 built one
scrolling page, which is neither. This splits it with the app's own `Segmented`
control: **Overview** is the four tiles and the two minute-long lines, **Detail**
is the logical processors, the volumes, the heaviest processes, and a card the
first version lacked.

That last card is the reason this is a slice and not a layout tweak. It is called
*Limits*, and it says two things: which tiles have no reading and why (the same
sentences the tiles carry, collected where someone diagnosing a machine goes
looking), and what this build does not collect at all — temperatures and
per-process CPU. A measurement page that stays silent about its blind spots reads
as complete, and the whole point of the reasons in this codebase is that it
should not.

The switch is page state, not a route: both views read the same frame, and the
sampler does not care which one is showing. Nothing about the thread, the JSON
or the tests changes.

## Slice 14 — per-process CPU, and what "busiest" means

Slice 6 deferred this in as many words: a rate needs two samples keyed by
something that survives pid reuse, a map that outlives a snapshot, and a rule for
a process that appears mid-interval. This is that slice, done before the two
machine checks because the Detail view could otherwise answer only "what is using
my RAM" while the question people arrive with is "what is using my CPU".

**Identity first, arithmetic second.** `core/sa6i-link-intel/src/cpu.rs` holds
`ProcessCpu`, a map from `ProcessKey { pid, created }` to the last reading.
`percent(key, at_ms, cpu_ms)` answers `NotSampledYet` for a process it has not
seen — never 0 — `NotSampledYet` again for two reads in the same millisecond
(a span of zero is not a rate), and `0.0` for a counter that went backwards.
`retain()` forgets processes that exited, so a machine that opens a program a
minute does not grow a map for ever. A recycled pid is a *different* key, so the
new process starts over instead of inheriting the old one's CPU: that is the bug
this type exists to prevent, and there is a test named after it.

**One more call on a handle already open.** `GetProcessTimes` runs on the same
`PROCESS_QUERY_LIMITED_INFORMATION` handle as the memory query: kernel plus user
time in 100 ns ticks, plus the creation stamp that makes the key. No new
privilege, no new API family; a failure is `CollectorFailed` on that row rather
than a dropped row or a zero. `TICKS_PER_MS` names the unit once.

**Percent of one core, like Task Manager.** A process with four busy threads reads
400 %, and the page does not divide by the core count behind your back. If a share
of the whole machine is ever wanted, it will be a second column with its own
label.

**The list changed, and so did its name.** `top_processes` orders busiest first,
then heaviest, then by pid: on a machine doing something the CPU column is the
answer, and on an idle one every rate is near zero and the list is the memory
hogs, which is what Task Manager shows by default too. A process whose rate is not
known yet sorts *below* measured ones rather than being called cheap. The Detail
card is now **Busiest processes**, with a CPU column, a dash for a process seen
once and a caption that says why; the Limits card's closing line drops
"per-process CPU" and keeps temperatures.

**On the wire** `processes[].cpu` is a number or `null`, under the same rule as
every other field: `null` for a process seen once, `12.5` for one measured. The
report line became `8 busiest: msedge.exe 1.2 GB 12.5 %, …`, and `metrics()`
publishes `process.{pid}.cpu_percent` only when there is a rate to publish.

Uncompiled, like the rest. The new risk is one signature: `GetProcessTimes` takes
the handle and four `&mut FILETIME` out-parameters, modelled on the existing call
in `desktop/app/src/win/mod.rs` rather than recalled.

## Slice 15 — the verification, as one command

The report has said "not verified" in every slice, and the six exit criteria have
been a table to read rather than a thing to run. That is the wrong shape for the
one step that is not mine to take: an operator who has to assemble `cargo test`,
two CLI invocations, a JSON check and a markdown table by hand will do it once,
badly, at eleven at night.

So `scripts/verify-m1.ps1` does the assembling. It builds `sa6i-link-cli`, takes
the minute of samples, asks for Task Manager's two numbers and does the ±3
arithmetic the plan asks for, checks the JSON contract from a **two**-sample run —
the process column is the one field that a single sample cannot demonstrate,
because a rate needs two — runs `tests/privacy.rs`, and, with `-Budget`, takes the
half hour and reads the CLI's exit code 3 rather than re-deriving a verdict from
text. It ends with `target/m1-verification.md`: the machine, what was measured,
and a row per criterion.

Two of the six rows come out as **eyes**, not pass: an old Windows, and a person
watching for a UAC shield. A script that printed PASS for those would be lying,
and this milestone has spent enough care on not doing that.

It does not replace `scripts/check.ps1`, which owns formatting, clippy, the whole
test suite, the headers and the dependency policy. The two are a sequence, and
`docs/plan/M1-VERIFY.md` says so: if `check.ps1` fails, nothing else matters yet.

Not verified, obviously: it is a PowerShell script written on a machine with no
Windows and no PowerShell. Its failure mode is the boring one — a parameter name
or a `ConvertFrom-Json` shape that is stricter than the file it parses — and the
fix is a line in the script, not a slice.

## Slice 16 — the Qt surface, checked against the code that does compile

Slices 10 and 13 wrote a bridge and a page that nothing here can build: no Qt, no
`rustc`, no window. The usual response is another paragraph of disclaimers. The
useful response is to check every API against code in this repository that *does*
compile and ship — the same discipline that settled the `GetProcessTimes`
signature — and to fix what does not match.

**What was checked, and matched.** `impl cxx_qt::Threading`, the empty
`impl cxx_qt::Initialize` inside the bridge module, `self.qt_thread()` and
`CxxQtThread<qobject::IntelHost>` all appear in `app.rs` and `calls.rs` in the same
shapes. `queue(..)` returns `Result<(), ThreadingQueueError>` and takes
`FnOnce(Pin<&mut T>)`, read from cxx-qt 0.10's own `threading.rs` rather than
recalled, so breaking the loop when the page has gone away is correct.

**Registration is where a page dies quietly.** `src/bridge/intel.rs` is in the QML
module's `rust_files` and `pub mod intel;` is in `bridge/mod.rs`; `MonitorPage.qml`,
`Sparkline.qml`, `Segmented.qml` and `Txt.qml` are all in `build.rs`'s `QML_FILES`;
`MainWindow.qml` carries the nav item, the `"monitor"` route and an icon that
exists. A page missing from that list loads as an empty URL and no test we have
would say a word, so it is worth having looked.

**The page's vocabulary.** All seven `Theme` tokens it uses exist; it sets only
properties `Txt`, `Card`, `Segmented` and `Sparkline` actually declare
(`role`/`muted`, default content, `options`/`value`/`picked(string)`,
`points`); and `interval_ms` reaching QML as `IntelHost.intervalMs` is the same
snake-to-camel step as `caps_revision` → `AppController.capsRevision`.

**The lockfile, mechanically.** Every path dependency declared in every workspace
manifest has an edge in its package's `Cargo.lock` entry — the class of failure
`cargo --locked` reports first, and the one hand-edited lock entries are most
likely to introduce. One crate (`tools/powertoys-extension`) is outside the
workspace and therefore absent by design.

**Two real defects, both invisible until a frame arrives.** The chart cards were a
`Repeater` over an array literal that mentioned `page.cpuPoints`, so the model's
identity changed on every frame and both cards — each with a `Canvas` — were
destroyed and recreated once a second, resetting the canvas each time. The model
now carries keys only and the points are looked up in the delegate. And the volume
track's width, `parent.width - 82 - 132`, could go negative in a narrow window;
it is clamped.

**One property read was aligned rather than fixed.** cxx-qt 0.10 generates a
getter method for a `#[qproperty]` *and* derefs the generated type to the Rust
struct holding the field, which is why the rest of this app reads properties as
fields (`object.update_busy`). The bridge called `object.samples()` in one place;
it now reads the field like every other bridge, so it does not depend on
auto-deref through a reference.

**Known cost, deliberately not paid blind.** The tile, core and process
`Repeater`s still rebuild once per frame, because a new frame is a new array. That
is churn rather than breakage — no `Canvas`, no animation that matters — and the
fix (a numeric model with an accessor so the delegates update in place) is a
three-block edit that wants a window to look at. The charts were fixed now
because a recreated `Canvas` loses its paint state, which is visible.

**Still unknown after all of this:** whether `Canvas` under Qt 6 accepts these 2D
calls, whether the nested `Flickable`/`Grid`/`Repeater` layout produces the
spacing the design asks for, and whether parsing one JSON frame a second is smooth
in QML. Those are the three the build will answer.

## Slice 17 — thresholds as data, so a rule can be run at someone else's numbers

M1's three rules read their thresholds from constants. That was right for M1 and
wrong for what comes next: the TOML front-end in `docs/plan/M2-RULES.md` exists to
change a threshold, and a rule that reads a global cannot be *shown* to change.
The fixtures would still pass, because nothing in them moves.

So the six numbers are a struct now. `Thresholds` carries the disk warning and
critical lines, the disk window, the memory line and window, and the uptime line;
`Rule::evaluate` takes `&Thresholds`; and `evaluate()` — the function the CLI, the
bridge and all eight golden scenarios already call — is a one-line wrapper over
`evaluate_with(snapshot, store, &Thresholds::default())`. Every existing caller and
every fixture is untouched, which is the point: if the refactor changed a verdict,
the scenarios would say so.

**One lie found and removed.** The uptime rule's evidence had `"14 days"` typed
into it as a string. With a threshold that can move, that string would have kept
saying fourteen while the rule fired at three — a finding citing a number it did
not use, in the one place this product promises there are none. It is derived from
the threshold now.

**Two tests, chosen for what they would catch.** The first pins every default to
the constant M1 shipped: a refactor that quietly moved a threshold would otherwise
pass, because the fixtures are evaluated with whatever the code says. The second
runs one 91 % volume for one ten-minute window at two thresholds — a finding at
90 %, nothing at 95 % — and a three-and-a-half-day machine against a three-day
line, asserting the evidence says `"3 days"` and that M1's fourteen-day line stays
silent on the same machine.

**Not done, on purpose:** no TOML, no parser, no new dependency, not one threshold
changed, `Cargo.lock` untouched. The front-end needs the rule bodies to be
parameterisable first; a file format on top of globals would have been a parser
with nothing to parse.

## Slice 18 — the two evidence paths that were collected and never published

`Snapshot::metrics()` is the contract a rule cites evidence against: a finding that
names a path no snapshot emits is a finding with no evidence. The M2 audit found
that the memory collector reads `commit_used` and `commit_limit` and `metrics()`
never emitted them — so the most useful memory figure a rule could cite (`"9.4 GB
of a 12 GB commit limit"`) was invisible to the evidence check.

Two lines fix it: `memory.commit_used_bytes` and `memory.commit_limit_bytes`. They
are published only when measured, like every other path, and the test that used to
check path names now checks the commit values too — plus that an unreadable commit
charge emits nothing rather than a zero.

The other half of that audit is deliberately still owed: `ProcessSample` does not
carry the creation stamp the CPU tracker keys on, so a per-process rule over ten
minutes could credit the wrong program after a pid is reused. Publishing it changes
the wire format and the process row, which makes it a slice rather than two lines —
and it belongs with the rule that needs it, not before it.

## Slice 19 — the CLI's wiring and the lockfile, checked the boring way

Slice 12 listed its two riskiest pieces as unverified: the clap wiring and the two
entries hand-added to `Cargo.lock`. Both are mechanical, so both can be read
instead of hoped for.

**A compile error, found by reading.** `IntelArg` carried
`#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum)]` *and*
`#[derive(Subcommand, Debug)]` — every one of those derives wrong for a subcommand:
`Debug` twice is a duplicate impl, `Copy` cannot hold the `Option<PathBuf>` inside
`--history`, and `ValueEnum` is for values, not for a `Subcommand`. Three errors on
one line, left behind by copying the derive line of a value enum four entries
above. It is `#[derive(Subcommand, Debug)]` now.

**What was checked around it.** `#[command(subcommand)]` is on the `Intel` field;
the pre-node dispatch returns `Result<i32>` into the block that becomes the exit
status, so `--budget`'s exit 3 survives; the defensive `bail!("intel runs before
the node starts")` arm is in `run()`; the imports `run_intel` needs (`Verdict`,
`WindowSummary`, `evaluate`, `Duration`, `Context`, `bail`) are all there; and the
flags the script passes are the ones clap derives — `interval_ms` becomes
`--interval-ms`, `no_findings` becomes `--no-findings`.

**The lockfile, structurally.** 527 packages; no dependency names a package that
is not in the file; no registry package is missing its checksum; no workspace
crate carries a `source`; and `sa6i-link-intel`, `sa6i-link-intel-win` and
`sa6i-link-cli` are all at 0.1.5, the workspace version, with their new edges
present. Checksums are the one thing this cannot verify — they are correct or
`cargo --locked` says so.

**What it does not prove.** That the crate compiles. It removes three known errors
and nothing more.

## Slice 20 — the rest of the blind code, read against the compiler's rules

Slice 19 found three errors in one derive line, so the sweep continued over
everything else written without a toolchain.

**Signatures against call sites.** `sample_window(u32, Duration, bool) ->
(SampleStore, Cost)` matches its `Cost { elapsed_ms: f64, per_sample_ms:
Vec<f64>, cpu_ms: Option<f64> }` construction; `Verdict::judge(u32, u64, &Cost)`
matches both the CLI and the standalone binary; `report_lines` and
`findings_lines` take what both callers pass; `SampleStore::len` exists and
`record_history`'s `&Path`/`&[Finding]` line up. No mismatch found.

**Two things I thought were guesses are precedents.** `#[auto_cxx_name]` is not
invented for the Intel bridge — `app.rs`, `prefs.rs`, `pairing.rs` and
`timeline.rs` all use it. And `Canvas` under Qt 6 with these exact 2D calls is not
an open question either: `WalkthroughPage.qml` ships and draws with the same
`getContext("2d")`, `reset`, `arc` and `roundedRect`.

**What is left of the "never verified" list** is now short and specific: whether
the compiler accepts the Win32, PDH, SQLite and cxx-qt calls as written, and
whether the page lays out as designed. Everything that could be read has been read;
the rest is the build's to answer.

## Slice 21 — `--json --budget` was a silent no-op

Reading the CLI's own control flow found a small lie of omission: `--json` returned
before the verdict was computed, so `sa6i-link intel snapshot --json --budget`
printed a JSON document and exited 0 whatever the sampler did. A flag that is
accepted and ignored is worse than one that is refused, because a script cannot
tell the difference from a passing run.

The verdict is now computed once, before the output decision, and:

- `--json --budget` gains a `budget` object in the payload (`Verdict` already
  serialises) and exits 3 on a miss, so one document and one exit code say the same
  thing;
- the text path prints the same four lines as before, from the same verdict —
  computed once, not twice.

The standalone binary got the same treatment, because it is meant to be the
headless twin and a twin that disagrees with itself is not one.

## What the collectors do not do, on purpose

Everything the plan listed for M1.1 is collected now, per-process CPU included
since slice 14. What is still absent is absent for a reason: temperatures need a
kernel driver: reading them without one means shipping a driver, and reading them
with one means shipping something no monitoring app should ask of a user.
(`GetPerformanceInfo` for a process count was evaluated and not shipped: nothing
uses it yet.)

Evaluated but not shipped: `GetPerformanceInfo` for a process count (easy, but
nothing yet uses it) and `GetVolumeInformationW` for filesystem names (only
useful once the UI shows them).

One measurement per slice was deliberate, not slow: a machine reporting bad
per-core numbers should not also be the machine whose PDH query is suspect.

## Verification

| Claim | Method |
| --- | --- |
| Type-level honesty | `MetricState` has no `Deref`, no `Default`-to-zero, and every accessor is fallible |
| Window arithmetic | Fixture stores built at 1 Hz; `held_for` tested for too-short history, a disqualifying sample, and pruning |
| Rule thresholds | Firing case and near-miss case per rule, including "network drive ignored", "worst volume wins", "unreadable volume is silent" |
| CPU maths | Tick deltas including an idle machine, a backwards counter, and a kernel/idle disagreement |
| Ordering | Worst-first, and identical ids across two evaluations of the same store |
| Process CPU identity | `cpu::tests`: first reading `NotSampledYet`, a recycled pid is a new process, a zero span is not a rate, a backwards counter is 0 % and not negative, exited processes are forgotten |
| Process ranking | `model::tests`: a busy 10 MB process above a 900 MB idle one, ties falling back to memory then pid, a measured rate above an unmeasured one |
| Process rate on the wire | `view::tests`: `processes[].cpu` is `null` for a process seen once and `12.5` for a measured one, and `metrics()` publishes no rate for the unmeasured row |
| Scenario fixtures | Every scenario was re-derived by an independent implementation (Python, written from the documented thresholds and windows, not from the Rust) — 8/8 agree with the expectations, so the fixtures are right for a reason other than "the code produced them" |
| SQL semantics | The exact statements (schema, upsert, ordering, retention cutoffs, the `MAX`-on-empty → `NULL` path) were replayed against a real SQLite in Python — 17/17 checks pass, so the assumptions the Rust makes are SQLite's actual behaviour, not my memory of it |
| Dependency graph | Both intel closures were recomputed independently in Python from the same lock — 62 and 74 crates, zero network-capable, which is what the Rust test asserts |
| GPU counters (slice 8) | Same documentation source as slice 7 for `PdhGetFormattedCounterArrayW`, `PDH_FMT_COUNTERVALUE_ITEM_W { szName: PWSTR, FmtValue }`, `PDH_MORE_DATA` and `PDH_CSTATUS_NO_OBJECT`; counter paths cross-checked against Microsoft's GPU counter documentation (`\GPU Adapter Memory(*)\Dedicated Usage` / `Dedicated Limit`) |
| PDH (slice 7) | Every signature and type read from the generated docs for `windows` 0.62.2 (`microsoft/windows-docs-rs`), then cross-checked against a working open-source user of the same module (Argus `pdh.rs`: `PdhOpenQueryW(PCWSTR::null(), …) == 0`, `value.Anonymous.doubleValue`) |
| Win32 surface (slice 4) | The module path, signature and class constant of `NtQuerySystemInformation` were checked against the `windows` 0.62.2 API listing rather than recalled; the per-processor struct is deliberately *not* declared, so only the first three of its six words are read |
| Every file | Delimiter balance and SPDX header checked mechanically (`balanced`, no long lines) |
| The CLI's wiring (slice 19) | `IntelArg`'s derives, the `#[command(subcommand)]` field, the pre-node dispatch's return type, the defensive arm and every import `run_intel` needs were read against the surrounding code; the lockfile was checked structurally (edges, sources, checksums present, versions) — three compile errors found and fixed |
| The Qt surface (slice 16) | Every cxx-qt and QML API used was matched against a file in this repository that compiles, plus cxx-qt 0.10's own `threading.rs` for `queue`'s signature; the QML module and page registrations were read out of `build.rs` and `MainWindow.qml`; the lockfile was checked mechanically. Two defects found and fixed, one pattern aligned |
| The verification script (slice 15) | Its JSON paths were read off the serde attributes in `model.rs` (`snapshot.processes[].cpu_percent.state`, snake_case, `MetricState` as `{state, value}`) rather than guessed, and the CLI flags it passes are the ones `IntelArg` declares. Not executed: no PowerShell here |

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

0. **Run it, on a machine with the toolchain.** Fifteen commits of Win32 calls,
   PDH calls, SQLite, a new dependency and a Qt page have never been through
   `rustc`. `docs/plan/M1-VERIFY.md` is the short version of this list, as a
   script that writes down what it found. By hand, in this order:

   ```powershell
   cargo fmt --all
   cargo test --locked -p sa6i-link-intel -p sa6i-link-intel-win
   cargo clippy --workspace --all-targets -- -D warnings
   cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- --json
   ```

   Then the two checks the CLI can answer without Qt — and, while the CLI is
   running, the one new line in the process list: a second `sa6i-intel-snapshot`
   run should show a rate for every process that was in the first sample, and a
   process that started between the two should show a dash rather than 0 %: `sa6i-link intel snapshot
   --samples 60 --interval-ms 1000 --average` beside Task Manager's Performance
   tab, and `--samples 1800 --interval-ms 1000 --budget` for the half hour. Two
   of M1's six exit criteria close that way, with the desktop app still unbuilt.
1. **Build the app.** `cargo build -p sa6i-link` on a machine with Qt and the
   Rust toolchain, then open Monitor and watch it for a minute. This is now the
   gate in front of everything else: M1.3 is the first slice that has never been
   looked at, and the failure modes I listed in its section are the ones to
   expect first (the cxx-qt handle type and `rust_mut`, the singleton
   registration, the `Canvas` calls).
2. Then M2: the TOML rule front-end and the twelve-plus Doctor rules. The audit
   is written — `docs/plan/M2-RULES.md` sorts the plan's rule list into what the
   collectors can answer today, what needs one more counter, and what needs a
   privacy decision — so the gate opens on a plan rather than a blank page.

(`sample_hourly` rollups stay unscheduled on purpose: they need a week of real
data before the rollup can be checked against what it summarises.)

The two M0 checks (`cargo xtask tokens --check`, `cargo check -p sa6i-link`) are
still outstanding on a machine with the toolchain; M1's code does not depend on
them, but the branch carries both.
