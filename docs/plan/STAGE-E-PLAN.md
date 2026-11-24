# Stage E — Testing, roadmap, risks, demo

Scope: what gets built, in what order, how it is proven, and what we refuse to
claim. Everything here is downstream of Stage C's contracts.

## 1. Testing strategy

| Layer | Method | Where |
| --- | --- | --- |
| Collectors | contract tests on shape and units, skipped when the API is absent on the host | `sa6i-link-intel-win` |
| Normaliser | property tests: overflow, negative deltas, missing → `Unknown` | `sa6i-link-intel` |
| Rules | golden fixtures: recorded snapshot JSON in, expected findings out; every rule needs a firing case **and** a near-miss | `sa6i-link-intel/tests/rules/` |
| Action registry | temp-dir sandbox, fault injection, precondition race, timeout, rollback assertion | `sa6i-link-intel/tests/actions/` |
| Explainer | fake HTTP server: valid, malformed JSON, unknown action id, oversized, timeout | `sa6i-link-intel/tests/explain/` |
| UI models | existing QML harness (`desktop/app/tests/qml`): model updates, Unknown and stale states | `desktop/app/tests` |
| End to end | `sa6i intel snapshot --json` diffed against a fixture manifest; CI runs it on Windows runners | `.github/workflows` |
| Performance | 30-minute soak: 1 Hz sampling, CPU under 1.5 %, RSS growth under 8 MB, no UI frame over 16 ms while sampling | manual + scripted |
| Accuracy | CPU and memory within ±3 % of Task Manager / Activity Monitor averages over 60 s | manual checklist |

Rules of the game: no rule without fixtures, no action without a failure-path
test, no merged code that makes CI's `xtask tokens --check` stale. Demo data
exists only behind `--demo`, and the UI labels it.

## 2. Roadmap

Estimates are focused-work ranges; they assume no unexpected platform blocker.

### M0 — Hygiene (1–2 days) — *prerequisite, no new features*

- Take the Android signing key out of Google Drive custody: move it and its
  password to a secret store plus an offline copy, confirm 2FA, and write the
  rotation decision tree. The key is **not** publicly shared (verified
  2026-11-16), so this is custody work, not an incident.
  ([SIGNING-KEY](../operations/SIGNING-KEY.md))
- Apply the Signal theme: `tokens.json` + `validate()` list + `render_kotlin()` +
  `cargo xtask tokens`, green `--check`.
- Regenerate the mark `.rgba` set and icon pipeline from the SVG.
- **Exit**: CI green, key no longer public, app still launches with the shortcut
  contract unchanged.

### M1 — The first slice: telemetry → evidence → Monitor (2 weeks)

`sa6i-link-intel`, `sa6i-link-intel-win`, collectors (CPU total/per-core via
`GetSystemTimes`, memory via `GlobalMemoryStatusEx`, volumes via
`GetDiskFreeSpaceExW`/`GetVolumeInformationW`, disk throughput via PDH English
counters, GPU memory via `QueryVideoMemoryInfo`, one process snapshot), sample
ring + SQLite rollups, Monitor Overview and Detail, `sa6i intel snapshot`.

**Exit**: numbers within ±3 % of Task Manager; 1 Hz for 30 min under budget;
Win7 renders `Unsupported` with reasons; CLI JSON stable and tested; no admin
prompt anywhere; nothing leaves the machine (verified by a network capture).

### M2 — Doctor rules and Pulse (1.5 weeks)

12–20 rules over M1's data (disk low, sustained high CPU, memory pressure,
pagefile thrash, startup weight, stale drivers, low disk throughput, GPU memory
pressure, long uptime, failing SMART readiness where readable), findings UI,
evidence drawer, Pulse page.

**Exit**: every rule has both fixtures; no finding rendered without evidence;
five-machine false-positive review documented; "clean machine" state looks
plausible, not empty.

### M3 — Action registry and audit (1 week)

Registry, risk levels, consent sheet, verification, audit log UI. Actions: open
native scan, open hosted cleaner, copy report, re-sample, dismiss with expiry.
Nothing destructive.

**Exit**: default-deny proven by test (unknown id rejected from UI, CLI and
model); fault-injection suite green; audit log reproduces any run exactly.

### M4 — Assistant, local first (1.5 weeks)

`ExplainContext`, redaction, Ollama provider, schema validation, template
fallback, provider badge, "show what will be sent", AI settings.

**Exit**: works with Ollama stopped, absent, slow and malformed; unregistered
action dropped; no cloud call without opt-in; payload preview byte-identical to
what is sent in a test harness.

### M5 — Clean, native (2–3 weeks)

Scan, category model, treemap, duplicate detection by size+hash, temp/cache
targets, risk-1 actions with dry-run default and recycle-bin rollback. Hosted
cleaner remains available and labelled.

**Exit**: allowlist tests for every category; dry run is the default; a
cancelled scan leaves no partial state; rollback restores from the recycle bin in
test.

### Later

Security module (**needs external integration** for real Defender/BitLocker
detail without admin — some readings will stay `Unknown`), Win7 polish, phone
side of Monitor, signed releases.

**A demo that survives technical questions exists after M4.** Security is a
module that can be honestly marked partial at that point.

## 3. Risk register

| # | Risk | Impact | Likelihood | Mitigation |
| --- | --- | --- | --- | --- |
| R1 | False-positive findings destroy trust faster than features build it | High | High | fixtures, hysteresis, confidence levels, no finding without evidence |
| R2 | New brand collides with existing Bloom/Hive/Graphite system and the Android generator | Medium | High | Signal is a theme, not a rewrite; generator edits are part of M0 |
| R3 | WMI/PDH latency freezes or stutters the UI | High | Medium | all collection off the UI thread; Win32 first, WMI only where unavoidable |
| R4 | Win7 gaps read as zeros and look like bugs | Medium | High | `Unsupported(os)` state, tested; Win7 is a degraded target |
| R5 | Model produces confident nonsense | High | Medium | schema + registry-bound ids + template fallback + "rules only" badge |
| R6 | An action damages a machine or deletes data | Critical | Low | risk ≤ 1 in the first slice, allowlists, dry run, rollback, audit |
| R7 | Clean scope creep toward hosted-cleaner parity | Medium | High | module ships in slices; parity is explicitly not promised |
| R8 | Licence contamination (GPL into MPL core) | High | Low | `deny.toml`, existing exceptions, no vendoring of BleachBit/LibreHardwareMonitor |
| R9 | Signing key custody (single account, password in plaintext beside it) | Critical | Low for leak, high for loss | secret store + offline copy, 2FA, rotation plan; no key rotation unless compromise is suspected |
| R10 | "Is it spying on me?" | High | Medium | local-only by default, payload preview, network capture in the demo |
| R11 | Android/desktop token divergence | Low | Medium | `--check` in CI, generator edits in the same PR |
| R12 | Demo fails on stage | High | Medium | offline-first demo path, `--demo` labelled fallback, pre-recorded clip |

## 4. Competition demo scenario (3 minutes, offline)

Set-up: a real laptop with a genuinely 92 %-full system drive and a phone paired.

| Time | Beat |
| --- | --- |
| 0:00 | Launch from the desktop shortcut. The Spine draws; Pulse reads "2 things need attention" — the number is from real data or the label says demo |
| 0:20 | Monitor: the CPU spike is attributed to the backup process by name; the sparkline shows last night's scheduled run |
| 0:50 | Doctor: drive C, 92 % full, **sustained 3 weeks** — open the evidence drawer: metric path, window, threshold, sample count |
| 1:20 | Clean: scan, 12.4 GB across categories, dry-run list first; run temp cleanup; free space changes; VERIFY lights up; the audit row appears |
| 1:50 | Assistant, running on Ollama locally: explains the finding in plain words and proposes one registered action. Kill Ollama live → the badge flips to "Rules only" and the same screen still explains itself |
| 2:30 | Pull the network cable. Everything still works; Link still reaches the phone over LAN; transfer a file |
| 2:50 | Close on three facts: no admin prompt, nothing left this machine (show the payload preview and the audit log), and every fix was verified |

Answer ready for the obvious question — "why not just use LibreHardwareMonitor
and BleachBit?" — with Stage B: licence-compatible, but one needs an admin driver
and the other needs a Python runtime; we take the taxonomy and write the rules.

## 5. What this product will not claim

Not antivirus. Not a "booster". Not a privacy VPN. Not a driver updater. Not
Windows 7 support (degraded rendering only). Not a health score. Not unlimited
cleanup — every category has a documented allowlist.

## 6. Approval gate

Stage F: this plan, Stages A–D, the module dependency diagram and the shared data
model are presented together. Implementation starts at M0 only after explicit
approval; M1 begins only after M0's exit criteria are met, and each milestone's
exit criteria are checked before the next begins.
