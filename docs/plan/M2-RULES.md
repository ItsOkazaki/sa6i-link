# M2 — the rules, audited before any are built

M2 fits M1 with a front-end and a dozen rules. This document is the audit that has
to come first, because the shape of M2 depends on facts that are cheap to check
now and expensive to discover halfway through: which rules the current collectors
can actually answer, which need one more counter, and which would need a new kind
of reading with a privacy cost attached.

**The gate still holds, with one exception.** No new rule is built until M1's
six exit criteria are closed on a real PC (`docs/plan/M1-VERIFY.md`). A rule is a
sentence about a machine; writing twelve of them against numbers nobody has
compared with Task Manager is how a diagnostics tool ends up confidently wrong.

The exception is **item 2 below, the loader**, and it is granted for a narrow
reason: the loader's proof is that the same recipes produce *byte-identical
findings* at the same numbers. It changes no verdict, adds no threshold, and its
test needs no machine. Waiving the gate for a change that cannot move a number is
different from waiving it for a change that decides one. The first machine turned
out to be Windows 7 SP1, which cannot build the toolchain at all
([`WIN7.md`](WIN7.md)), so "wait for a real PC" and "wait forever" had become the
same instruction. What this page
settles is *which* twelve, with what evidence, and what each one costs.

## What M1 can be asked today

`Snapshot::metrics()` is the contract rules cite evidence against: a finding that
names a path no snapshot publishes is a finding with no evidence. Today it
publishes:

```
cpu.percent                        memory.percent_used
cpu.core.{n}.percent               memory.total_bytes     memory.available_bytes
volume.{letter}.percent_used       volume.{letter}.free_bytes   volume.{letter}.total_bytes
disk.read_bytes_per_second         disk.write_bytes_per_second
gpu.adapter.{n}.dedicated_used_bytes   gpu.adapter.{n}.dedicated_limit_bytes
process.{pid}.working_set_bytes    process.{pid}.cpu_percent
system.uptime_seconds
```

Three things are collected but **not published**, and each is a one-line change
that a rule needs before it can cite them: `memory.commit_used` and
`memory.commit_limit` (the collector reads them; `metrics()` does not emit them),
and the process's creation stamp (`ProcessKey.created`), which lives in the
rate tracker and never reaches the snapshot.

## The catalogue

Twelve rules that ship with M2, sorted by what they need. Severity is the
`findings::Severity` word, so the page never carries it in colour alone.

| id | measured from | window | severity | state |
| --- | --- | --- | --- | --- |
| `disk.low_free_space` | `volume.{letter}.percent_used` | 10 min | Warning → Critical at 97 % | **shipped in M1** |
| `memory.pressure` | `memory.percent_used` | 2 min | Notice | **shipped in M1** |
| `system.long_uptime` | `system.uptime_seconds` | instant | Info | **shipped in M1** |
| `cpu.sustained_high` | `cpu.percent` | 10 min | Warning | ready |
| `cpu.one_core_pinned` | `cpu.core.{n}.percent` vs `cpu.percent` | 10 min | Notice | ready |
| `disk.filling_fast` | `volume.{letter}.free_bytes` delta | 30 min | Notice | ready |
| `gpu.vram_pressure` | `gpu.adapter.{n}.dedicated_used_bytes` / `…_limit_bytes` | 5 min | Warning | ready, silent where the limit is 0 |
| `process.runaway_cpu` | `process.{pid}.cpu_percent` | 10 min | Notice | ready, with the identity caveat below |
| `process.memory_growth` | `process.{pid}.working_set_bytes` | 30 min | Notice | ready, same caveat |
| `memory.commit_pressure` | `memory.commit_used` / `memory.commit_limit` | 5 min | Warning | needs the two `metrics()` lines |
| `disk.slow_transfers` | `Avg. Disk sec/Transfer` | 10 min | Warning | needs one more PDH counter on the query already open |
| `memory.paging` | `Pages Input/sec` | 5 min | Warning | needs a second PDH query (`Memory`) |

### The caveats that decide whether a rule is honest

**`gpu.vram_pressure` and integrated GPUs.** The `Dedicated Limit` counter is
genuinely 0 on an iGPU, and slice 8 already refuses to divide by it. The rule must
therefore run only on adapters that publish a limit, and say nothing about the
others — not "0 %", and not "cannot tell" on a page that looks otherwise complete.
The Limits card already lists unmeasured tiles; this is the same rule.

**`process.*` and pid reuse.** The rate tracker keys on pid *and* creation stamp,
but the snapshot carries only the pid. A rule that accumulates a process over ten
minutes is therefore creditable to the wrong process if a pid is recycled inside
that window. Two honest options: publish `created` in `ProcessSample` so the rule
can key on it (one field, one `metrics()` change), or require the *name* to match
across every sample in the window and restart the window when it does not. The
second is cheaper and weaker. This audit prefers publishing the stamp: it is the
same fact the tracker already uses, and a rule that can be wrong about *which*
program is at fault is the exact failure this codebase exists to avoid.

**`disk.filling_fast` is a rate of a rate.** Free space falling 5 GB in half an
hour is a fact; "your disk will fill tomorrow" would be a forecast. The finding
says the first thing only. The store holds 4096 samples at 1 Hz, which is 68
minutes, so the window fits today — and a 30-minute window needs the app to be
open for 30 minutes, which is why the wording must not imply a background service
that does not exist.

**`disk.slow_transfers` is the one rule that answers "why is it slow".**
Bytes per second is throughput; latency is what a person feels. `PhysicalDisk` is
already queried for read/write bytes, so `Avg. Disk sec/Transfer` is one more
counter path on the same query and one more `metrics()` field. It is also the
counter most likely to need a per-disk breakdown later; the rule cites `_Total`
and says so.

## Three rules that need a decision, not a slice

| id | what it would need | why it is not in the twelve |
| --- | --- | --- |
| `startup.weight` | registry `Run` keys, the Startup folder, Task Scheduler | it reads *user data* — program names and paths — and M1 has so far read only counters. That is a privacy decision for the product, not a collector to slip in. If it ships, the finding names the entries and never their command lines |
| `drivers.stale` | `Win32_PnPSignedDriver` dates | a date is not a defect: a 2019 touchpad driver that works is not a problem, and the rule would fire on every ageing laptop. If anything ships here it is `drivers.problem` from a device's error code, not age |
| `disk.smart_readiness` | `IOCTL_STORAGE_PREDICT_FAILURE` | works on some drives, needs elevation on others, and returns nothing over most USB bridges. A rule that is `Unsupported` on half the fleet and `Critical` on the other half is a rule that teaches people to ignore red. It can ship as an explicitly `Unsupported` row with the reason, never as a promise |

The plan's M2 list also names "pagefile thrash" and "low disk throughput": the
first is `memory.paging` above, deliberately measured by pages read rather than by
the pagefile's size (a big pagefile is configuration, not a fault); the second is
`disk.slow_transfers`.

## The front-end: TOML, and a loader that refuses things

The point of the front-end is not that rules become data. It is that a rule cannot
exist without a **firing case and a near-miss**, and that the loader proves it
every time the app starts.

```toml
# rules/disk.toml
[[rule]]
id = "disk.low_free_space"
severity = "warning"
confidence = "certain"
requires = ["volume.*.percent_used"]
warn_percent = 90.0
critical_percent = 97.0
sustained = "10m"
firing = "09-disk-ninety-one-percent"
near_miss = "10-disk-eighty-nine-percent"
```

The loader refuses a file — with the rule and the reason named — when:

- the `id` is not in the compiled registry, so a TOML file cannot invent a rule
  the code does not implement (default deny, the same shape M3's action registry
  will use);
- an unknown key appears, so a typo like `warn_pct` fails loudly instead of being
  silently ignored and leaving the default threshold in place;
- a `requires` path is one `metrics()` never publishes, so evidence cannot cite it;
- `firing` or `near_miss` names a scenario that does not exist, or that another
  rule already claims;
- the firing case does not produce this finding, or the near-miss does produce it —
  the harness from slice 3 already knows how to evaluate a recipe, so this is a
  check, not a new mechanism;
- a threshold is outside the range the rule declares as possible (a
  `warn_percent` of 900 is not a stricter rule, it is a typo).

With no TOML file present the compiled defaults apply, so the app cannot start
with zero rules — the front-end overrides; it is not the only source.

## Fixtures: what a near-miss has to be

The near-miss is where a rule earns its keep, and the cheap version — "a machine
nowhere near the threshold" — proves nothing. Each rule gets two, and both are
recorded in `tests/scenarios/`:

1. **Adjacent**: just under the threshold, held for the whole window
   (89.9 % for 10 minutes, not 50 % for one sample).
2. **Looks-like-it-but-isn't**: the shape that would fool a naive rule — a network
   volume at 99 %, a process that exits mid-window, an iGPU whose limit is 0, a
   volume whose numbers are unreadable (`Unknown`, which must stay silent rather
   than fire).

Both are required by the loader, not by review, and both are the reason a rule
takes an afternoon rather than an hour.

## The false-positive review

M2's exit criterion says five machines, documented. The template is one row per
finding per machine:

| machine | what it was doing | finding | true? | why |
| --- | --- | --- | --- | --- |

A finding that was wrong gets its rule's threshold or window changed *and its
fixture updated in the same commit*, because the pair is what keeps the change from
being a guess. A finding that was right for a reason we did not anticipate gets a
sentence in the rule's doc comment — that is the cheapest documentation this
project will ever get.

## What the "clean machine" looks like

The plan asks that the clean state look plausible rather than empty. Current
answer, already implemented: the all-clear sentence with the count of what was
measured, the four tiles, the sparklines and the Limits card — so a machine with
nothing wrong still shows the machine. M2 adds one thing to that: the rules that
did not run, and why (`requires` unavailable), because "nothing found" and
"nothing looked" must not look the same on screen.

## Order of work, once the gate opens

1. **The thresholds, as data** — *done in M1's slice 17*: `rules::Thresholds`
   carries all six numbers, `Rule::evaluate` takes it, and `evaluate_with` runs the
   fixtures at any other set. Nothing changed for callers: `evaluate` passes the
   defaults.
2. **The loader and the validator**, with fixtures only — no new thresholds, the
   three M1 rules expressed as TOML and proven to produce byte-identical findings
   from the same recipes. That is the test that the front-end did not change a
   verdict.
3. **The rules that need a `metrics()` line** — `memory.commit_pressure` is
   unblocked (slice 18 published `memory.commit_used_bytes` and
   `memory.commit_limit_bytes`); the process creation stamp is still owed, and
   belongs with `process.runaway_cpu`.
4. **`Avg. Disk sec/Transfer`**, then `disk.slow_transfers` and `memory.paging`.
5. **The five-machine review**, then whatever the review changed.

Dependencies: `toml` is already in `Cargo.lock` through the workspace, so the
front-end should not add a crate — but the version in the lock is the version
M2 gets, and `cargo --locked` is the check.
