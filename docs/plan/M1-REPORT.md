# M1 report — telemetry, evidence, rules

The first slice of the intelligence core: measure a machine, prove what was
measured, and turn it into findings that carry their own evidence. No UI yet,
no model, no persistence beyond memory.

## What exists now

| Piece | Where | State |
| --- | --- | --- |
| The machine model | `core/sa6i-link-intel/src/model.rs` | **done** — `MetricState`, `Snapshot`, CPU/memory/volumes/uptime |
| Findings and evidence | `core/sa6i-link-intel/src/findings.rs` | **done** — severity, confidence, evidence, rendering |
| The rule engine | `core/sa6i-link-intel/src/rules.rs` | **done** — 3 rules, hysteresis, stable ordering |
| Sample history | `core/sa6i-link-intel/src/store.rs` | **done** — bounded ring, `held_for` windows |
| Windows collectors | `core/sa6i-link-intel-win/src/lib.rs` | **done** — CPU, memory, volumes, uptime, no admin |
| Headless proof | `core/sa6i-link-intel-win/src/bin/sa6i-intel-snapshot.rs` | **done** |
| Monitor page, persistence, TOML rules, disk/GPU/process collectors | — | **not started** (see below) |

```powershell
cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot
cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- --samples 700 --interval-ms 1000
cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- --json
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
| Every file | Delimiter balance and SPDX header checked mechanically (`balanced`, no long lines) |

**Not verified: it has not been compiled.** There is no Rust toolchain in this
sandbox. The code was written against the calling conventions already used in
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
2. **M1.2 — persistence:** SQLite rollups per the retention table in
   `docs/architecture/INTELLIGENCE-CORE.md` §9, with the ring unchanged in front.
3. **M1.3 — the Monitor page:** `IntelHost` (cxx-qt), 1 Hz property updates, the
   Overview tiles and the sparklines that draw gaps as gaps.
4. Then M2: the TOML rule front-end and the twelve-plus Doctor rules.

The two M0 checks (`cargo xtask tokens --check`, `cargo check -p sa6i-link`) are
still outstanding on a machine with the toolchain; M1's code does not depend on
them, but the branch carries both.
