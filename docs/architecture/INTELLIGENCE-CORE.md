# Stage C — Intelligence core architecture

Decisions applied: D1 keep Qt Quick/QML + Rust · D2 native Clean engine with
the hosted cleaner as a labelled fallback · D3 Windows 10/11 first · D4 first
slice = telemetry → evidence → Monitor → Doctor rules → Assistant on that model.

This document defines the contracts. It contains no implementation.

---

## 1. Principles

1. **Deterministic core, optional model.** Every finding is produced by a rule
   over measured data. The model can explain and prioritise; it can never be
   the origin of a fact or of an action.
2. **Evidence or silence.** No metric, finding or recommendation exists without
   the sample(s) that produced it. An unavailable measurement is `Unknown`, a
   first-class state, never `0`.
3. **Read-only first.** Monitor, Doctor and Security never write to the system.
   Only registered actions mutate anything, one at a time, after consent.
4. **Least privilege.** Nothing in the first slice requires administrator
   rights; elevated actions are refused until an elevated helper exists.
5. **The product works offline, without AI, and without an account.**

---

## 2. Crate layout

```
core/
  sa6i-link-core/          existing: link, protocol, capability matrix   (MPL-2.0)
  sa6i-link-intel/         NEW: telemetry model, rules, findings,
                                 action registry, audit log               (MPL-2.0)
  sa6i-link-intel-win/     NEW: Windows collectors (windows crate)        (MPL-2.0)
  sa6i-link-cli/           existing: gains `sa6i intel snapshot|findings` (GPL-3.0+)
desktop/app/
  src/intel/               NEW: IntelHost (cxx-qt bridge), workers        (GPL-3.0+)
  qml/pages/monitor/       NEW: Monitor, Doctor, Security, Assistant pages
sa6i/clean/                existing: hosted cleaner + native host adapter (unchanged)
```

Rules of the split: `sa6i-link-intel` knows nothing about Windows, Qt or HTTP;
`-intel-win` implements a trait; the CLI and the GUI consume the same engine, so
a rule that fires in the UI can be reproduced from a terminal and in a test.

## 3. Data flow

```
 collectors ──▶ normalize ──▶ Snapshot (ring + SQLite) ──▶ rules ──▶ Findings
 (per metric)   (units,          │                                     │
                 missing→Unknown)│                                     ▼
                                  │                            correlate / rank
                                  │                                     │
                                  └──────────────▶ context ──▶ explain (optional model)
                                                                         │
                                                                         ▼
                                   ActionRegistry ──▶ consent ──▶ execute ──▶ verify
                                        (whitelist)               │            │
                                                                  └─▶ audit log ┘
```

## 4. Data model (normative shapes)

```rust
pub enum MetricState<T> { Value(T), Unknown(WhyUnknown), Unsupported(OsVersion) }

pub struct Sample<T> { pub value: MetricState<T>, pub at: Timestamp, pub source: SourceId }

pub struct Snapshot {
    pub seq: u64,
    pub taken_at: Timestamp,
    pub os: OsFacts,              // build, edition, secure boot, uptime
    pub cpu: CpuSample,           // total, per-core, frequency
    pub mem: MemSample,           // physical, commit, pagefile
    pub disks: Vec<DiskSample>,   // per volume + per physical disk
    pub gpu: Option<GpuSample>,
    pub procs: ProcessSummary,    // top-N by cpu/mem, counts
    pub thermal: MetricState<()>, // Unsupported until an elevated helper exists
}

pub struct Finding {
    pub id: FindingId,            // stable, rule id + subject key
    pub rule: RuleId,
    pub severity: Severity,       // Info | Notice | Warning | Critical
    pub confidence: Confidence,   // Certain | Likely | Possible
    pub subject: Subject,         // process / volume / startup item / metric
    pub evidence: Vec<Evidence>,  // metric path, sample range, computed value
    pub explain: ExplainTemplate, // deterministic text, always present
    pub actions: Vec<ActionId>,   // candidates, never auto-run
    pub first_seen: Timestamp,
    pub last_seen: Timestamp,
}

pub struct Evidence {
    pub metric: MetricPath,       // "disk.C.percent_used"
    pub window: (Timestamp, Timestamp),
    pub observed: String,         // rendered with units
    pub threshold: Option<String>,
    pub sample_seq: Vec<u64>,     // which samples prove it
}
```

`MetricPath` is a dotted string addressed by rules; the same string is what the
UI shows when the user asks "why?". Evidence is not prose: it is the data, with
a renderer on top.

## 5. Rule format

Declarative TOML, compiled into the binary, versioned, one file per module
(`rules/doctor/*.toml`, `rules/security/*.toml`). Rules never contain shell
commands and never contain free-form claims.

```toml
id = "disk.low_free_space"
module = "doctor"
severity = "warning"
confidence = "certain"
subject = "volume"
requires = ["disk.*.percent_used"]        # metrics that must be measurable

[[when]]
metric = "disk.*.percent_used"
op = ">"
value = 90
for = "10m"                               # hysteresis: sustained, not a blip

[explain]
title = "Drive {letter} is almost full"
body = "{free} free of {total} ({percent}%). Windows needs headroom to keep working."
why = ["disk.{letter}.free_bytes < 10% for 10 minutes"]
actions = ["clean.open_native_scan", "clean.open_hosted"]
```

Rules are tested against recorded snapshots (see §10), so a rule either has
fixtures or it is not allowed to ship.

## 6. Action registry

```rust
pub struct ActionSpec {
    pub id: ActionId,
    pub title: &'static str,
    pub risk: Risk,               // 0 ReadOnly | 1 ReversibleLocal | 2 Destructive | 3 Forbidden
    pub requires_admin: bool,
    pub preconditions: Vec<Precondition>,  // re-checked immediately before running
    pub verify: VerifySpec,       // which metrics must change, and how
    pub rollback: Option<Rollback>,
    pub scope: Scope,             // protected paths, max bytes, allowed roots
}
```

Invariants enforced by the registry (not by convention):

- **Default deny**: an `ActionId` that is not in the compiled registry cannot be
  invoked by the UI, the CLI or the model.
- **Risk 3 is unreachable**: no format, no registry edit, no driver install, no
  service stop of security products, no deletion outside a computed allowlist.
- **No shell strings**: executors take typed arguments; there is no `cmd /c`.
- **One at a time**, per-machine lock, timeout, and a hard abort if the
  preconditions no longer hold.
- **Consent** is per invocation, shows measured evidence and the exact effect,
  and cannot be pre-granted globally.
- **Audit**: append-only record of every attempt — who, what, args, pre-state,
  post-state, verification result, rollback taken.

First slice ships only Risk 0/1 actions: open a page, copy a report, re-scan,
restart a collector, open native scan. Nothing destructive.

## 7. AI provider abstraction

```rust
#[async_trait]
pub trait Explainer {
    async fn explain(&self, ctx: &ExplainContext) -> Result<Explanation>;
    fn capabilities(&self) -> Caps;   // context window, json mode, streaming
}

pub struct ExplainContext<'a> {   // the ONLY thing a model ever sees
    pub findings: &'a [Finding],
    pub snapshot_digest: &'a SnapshotDigest,  // numbers, no paths with usernames
    pub allowed_actions: &'a [ActionId],
    pub locale: Locale,
}
```

Contract:

1. **Input is structured, never free text.** The model never receives raw
   conversation history, file contents, or the user's registry.
2. **Output is validated.** JSON schema per version; unknown `ActionId`s are
   dropped before display; if validation fails, the deterministic template is
   shown instead.
3. **The model cannot act.** There is no tool-calling path to execution; it can
   only name registry ids, and the UI still asks for consent.
4. **Redaction** before send: user names, file paths outside allowlisted roots,
   device names, IPs. Logged as a redaction count, not silently dropped.
5. **Local first**: `OllamaExplainer` at `127.0.0.1:11434`. Cloud providers are
   a separate trait object, disabled by default, with an explicit opt-in and a
   visible "this text leaves your PC" preview.
6. **Degradation**: no runtime → templates; slow runtime → templates after a
   timeout; the UI shows which mode produced the text.

## 8. Qt/QML bridge

`IntelHost` (cxx-qt `QObject`), one per window, no blocking calls:

| Surface | Kind | Notes |
| --- | --- | --- |
| `snapshot` | read-only property | updated at 1 Hz from the collector thread |
| `monitorModel`, `findingsModel` | `QAbstractListModel` | diffed, not rebuilt |
| `startSampling(profile)` / `stopSampling()` | invokable | profiles: idle / normal / detailed |
| `explain(findingId)` | invokable (async) | returns template immediately, model text later |
| `runAction(id, consentToken)` | invokable | errors are typed, never silent |
| `actionProgress`, `findingAdded` | signals | progress carries verification state |

UI honesty rules: `Unknown` renders as "Not available on this system" with the
reason; stale data is visibly stale (timestamp + dimmed); there is no skeleton
that fakes numbers.

## ## ## 9. Persistence

SQLite via the existing `rusqlite` (bundled), in the app's data dir. Slice 2
implements the first two tables; the rest arrive with the features they serve.

| Table | Contents | Retention | Shipped |
| --- | --- | --- | --- |
| `sample` | the whole `Snapshot` as JSON, keyed by `taken_at`, 1/min | 24 h raw | yes |
| `finding` | `first_seen`, `last_seen`, severity, the finding JSON | 30 days | yes |
| `sample_hourly` | rolled up | 30 days | no — needs a week of raw data first |
| `action_run` | args, pre/post state, verdict | permanent (audit) | no — actions are M3 |

Details that are load-bearing:

- **One row per minute, not per second.** A day is 1,440 rows; the second a rule
  needs is already in the ring. The interval is enforced in `History::record`,
  and the newest stored `taken_at` is read back on open, so restarting the app
  does not write a burst.
- **A clock that goes backwards cannot rewrite the past.** A sample whose wall
  clock is behind the newest stored one is stored as "the moment after it", so
  `ORDER BY taken_at` still means "in the order things happened".
- **Findings are upserts keyed by the stable id**, so `first_seen` is the first
  time this machine ever had that problem. That is the sentence the UI shows
  ("full for three weeks"), and it is why a finding is not just a snapshot row.
- **`PRAGMA user_version` is checked on open**; a database written by a newer
  Sa6i is refused with a typed error rather than mis-read.
- **WAL**, so a reader (the UI) never blocks the recorder (the sampler).
- History is **opt-in** (`--history PATH` on the CLI): nothing is written to
  disk unless a caller asks for it. A corrupt or locked database degrades to
  in-memory only, and says so.

## ## ## 10. Testing strategy

| Layer | Method |
| --- | --- |
| Collectors | Contract tests: shape and units only, skipped when the OS lacks the API. No value assertions against a live machine |
| Normalizer | Property tests: units, overflow, missing → `Unknown` |
| Rules | **Golden fixtures**: `core/sa6i-link-intel/tests/scenarios/*.json`, each rule with a firing case and a near-miss case; the harness fails if a rule in `RULES` lacks either |
| Actions | Temp-dir sandboxes, fault injection, precondition race, timeout, rollback |
| Explainer | Fake HTTP server; schema-rejection cases (unknown action, malformed JSON, oversize) |
| UI | Existing QML test harness (`desktop/app/tests/qml`) for models and states |
| End-to-end | CLI: `sa6i intel snapshot --json` diffed against a fixture manifest |

A rule or action without tests is not merged; demo data exists only behind a
`--demo` flag that the UI labels.

## Slice 1 status (where the code deviates, on purpose)

| Contract | Slice 1 | Why |
| --- | --- | --- |
| §4 data model | `Snapshot` carries CPU (total and per-core), memory, volumes, uptime; frequency, GPU, thermal and process summary are absent rather than empty | a field that is always `Unknown` teaches the UI nothing |
| §4 per-core | `CpuSample.per_core` is the calling thread's processor group, not every logical processor | `NtQuerySystemInformation(SystemProcessorPerformanceInformation)` answers per group; the documented classes do not expose all groups, and the buffer routine is worth trusting before the undocumented sibling gets used. `per_core.len()` is the number measured, and the UI says that instead of implying a total |
| §5 TOML rules | rules are Rust functions with named constants, behind the same `RuleDef` | the front-end compiles into the same struct; shipping a parser before one rule works would be backwards |
| §9 SQLite | `sample` stores the whole snapshot as JSON, not compact per-metric rows; no `sample_hourly` yet | one row a minute is a few hundred kilobytes a day, and a schema that mirrors `Snapshot` cannot drift from it. Rollups wait until there is a week of raw data to validate them against |
| §9 SQLite | history is written only when asked (`History::open`) | a diagnostics tool that silently starts writing to disk on first launch is a privacy decision made by accident |
| §2 crate names | as planned: `sa6i-link-intel`, `sa6i-link-intel-win` | — |

See `docs/plan/M1-REPORT.md`.

## ## ## 11. Boundaries with existing code

- No changes to Link transport, protocol or `features.rs` semantics.
- Capability matrix gains entries (Monitor available, thermal unavailable) rather
  than new parallel logic.
- `tracing` gains an `intel` target; logs never contain full paths by default.
- The hosted cleaner keeps working exactly as today, behind its existing guard;
  the native Clean engine is additive and separately branded in the UI.

## ## ## 12. Risks specific to this architecture

| Risk | Mitigation |
| --- | --- |
| WMI/COM latency freezes UI | all collection off the UI thread; WMI only where no Win32 API exists |
| Localised PDH counters break metrics | `PdhAddEnglishCounter` only |
| Win7 gaps read as zeros | `Unsupported(os)` state, tested |
| Model invents advice | schema validation + template fallback + registry-bound action ids |
| Rule sprawl | golden fixtures required; rule ids reviewed like code |
| Action mistakes | Risk 0/1 only in first slice; protected-path list; audit log |
