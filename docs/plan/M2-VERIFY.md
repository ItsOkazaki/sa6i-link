# Verifying M2 on a machine that can decide

M2 is twelve rules, thirty-four fixtures and twenty-five thresholds, and not one
line of it has been through `rustc`. That is the state of the milestone, not a
footnote to it: the sandbox that wrote M2 has no Rust, no Qt, no Windows and no
compiler, so every claim below is either *written and simulated* or *not yet
known*, and the two are never mixed in the same sentence.

This page is the operator's side of that. Four commands, what each one answers,
what it cannot answer, and a table of how to provoke each rule on purpose so a demo
is a demonstration rather than an assertion.

M1's equivalent is [`M1-VERIFY.md`](M1-VERIFY.md); read its first section once for
the toolchain, because it is the same toolchain and it bit the first runner. This
page does not repeat it.

## The four commands

| Command | What it proves | What it cannot |
| --- | --- | --- |
| `cargo test --locked -p sa6i-link-intel` | Every rule produces exactly the findings its fixtures promise, and every rule both fires and stays quiet somewhere (`every_rule_has_a_firing_case_and_a_near_miss`). That is 34 fixtures and the unit tests around them. | Nothing about Windows. The fixtures are recipes, not captures. |
| `cargo test --locked -p sa6i-link-intel --test privacy` | Neither intel crate has a path to a socket: the dependency graph is asserted, not reviewed. | That the process opens no file it should not; that is a different test on a different day. |
| `cargo run --locked -p sa6i-link-cli -- intel snapshot --samples 5 --interval-ms 1000` | The collector produces the metric paths the rules declare in `requires`, on this machine, in this locale. This is the only command here that needs Windows. | That the rules fire; five samples is four windows short of almost all of them. |
| `python3 scripts/check-fixtures.py` | The same fixtures, an independent re-implementation of all twelve rules, the TOML files flattening to the compiled defaults, and the fixture key names matching the `deny_unknown_fields` structs. Runs without a compiler, which is why it exists. | Anything at all about the Rust. If the two disagree, one of them is wrong and this file is not the arbiter. |

The first three are the milestone. The fourth is the second opinion, and it is the
only one that can run on the machine M2 was written on.

A fifth command is not a test but a proof of currency, in the same shape as
`cargo xtask tokens --check`:

```powershell
python3 scripts/fixtures-report.py --check
```

[`M2-FIXTURES.md`](M2-FIXTURES.md) is generated from the rule files and the
fixtures, and that command fails if the page and the directories have drifted
apart. It is the same guard the deck has, for the same reason: a document that
describes generated things goes stale silently, and a stale page in a milestone
report is a claim nobody re-read.

## What passing looks like

```text
$ cargo test --locked -p sa6i-link-intel
test result: ok. <every test> passed; 0 failed; 0 ignored
```

The count is deliberately not written down here: M2 added tests in three files and
the number moves with any later slice, so a figure in this page would be stale
before it was read. What matters is that the run ends in `ok` and that no test is
skipped.

```text
$ python3 scripts/check-fixtures.py
fixtures: 34
every fixture produces exactly what it promises
all 25 threshold fields match the compiled defaults
24 fixtures claimed, none twice
```

If the fixture count is 34 and the thresholds are 25 but the last line says fewer
than 24 claimed names, a rule lost a scenario. Any other difference between that
output and this page means the page is stale, not the code.

## What will bite, in the order it will bite

**The borrow checker, first, in `gpu_vram_pressure`.** The rule holds a
`&GpuAdapter` borrowed from the snapshot while it asks the store for a window, and
the closure captures the adapter's instance name by move. That is written to
compile, and it has never been tried. If it does not, the fix is one line — clone
the instance, drop the reference, index into the adapter list afterwards — and it
is a compile error rather than a wrong number, which is the good kind.

**A fixture key with a typo.** Every fixture struct is `deny_unknown_fields`, so
`"gpu"` for `"gpus"` is not a default: it is a fixture the harness refuses to
read, with serde's message naming the key. `check-fixtures.py` checks the names
for the same reason, and it is the check that would have caught it before the
compiler did.

**A counter that does not exist.** On Windows 8.1 and older there is no
`\GPU Adapter Memory` counter set at all, so `GpuCounters::new` returns
`Unsupported(NotOnThisWindowsVersion)` and the VRAM rule says nothing. That is the
designed answer, and the Windows 7 machine should show it. The failure to look for
is the opposite: an `Unsupported` on Windows 10 with a WDDM 2.0 driver, which means
the counter path is wrong rather than the machine.

**A window nobody stayed open for.** Two rules need half an hour of history
(`disk.filling_fast`, `process.memory_growth`) and four need five or ten minutes.
A sixty-second run cannot fire them, and a run that reports "nothing found" after a
minute has not disproved them. The store holds 4096 samples at 1 Hz, which is 68
minutes: the windows fit, the patience is the variable.

**A deployment file that cannot be trusted.** `RuleFile::parse` refuses a TOML file
that names an unknown rule, names one twice, uses another rule's key, gives a
number outside the range its rule can mean, inverts a warning and a critical
threshold, writes a duration with no unit, cites a metric path no snapshot
publishes, disagrees with the code about a severity or a `requires` list, or claims
a scenario that does not exist or is already claimed. Each refusal is a `Refusal`
value naming the rule and the key, and the tests that prove them are the module at
the bottom of `rules_file.rs` — one test per variant, each with the file that must
be refused.

The way to hand such a file to the app is `--rules`, and it is one flag:

```powershell
cargo run --locked -p sa6i-link-cli -- intel snapshot --rules demo.toml --samples 30
```

A refused file stops the run before the first sample, prints every reason on
stderr, and exits 2 — distinct from 1, which is a broken build, and from 3, which
is a missed sampling budget. That ordering is deliberate: asking a machine for half
an hour of history and only then refusing the numbers it is judged by is the wrong
way round.

The flag also makes an honest demo possible without waiting half an hour — and
this is the one place the pitch has to be careful. A demo file like this

```toml
[[rule]]
id = "cpu.sustained_high"
severity = "warning"
confidence = "likely"
requires = ["cpu.percent"]
warn_percent = 60.0
sustained = "30s"
```

makes the CPU rule fire in thirty seconds instead of ten minutes. Showing it is
fine as long as the sentence that goes with it is true: *the numbers are a file,
and this file is a demo*. The machine did not become busier because the threshold
moved, and saying it did is the failure mode this whole design exists to avoid.

## Provoking each rule, honestly

A demo where nothing fires is a demo of a quiet machine. These are the cheapest
honest ways to produce each finding; every one of them is a real condition on a
real PC, not a threshold that was lowered to make a screenshot.

| Rule | What to do | How long |
| --- | --- | --- |
| `system.long_uptime` | Nothing — it fires on its own after fourteen days. | instant |
| `cpu.sustained_high` | Compress a large folder on all cores, or run a render. | 10 min |
| `cpu.one_core_pinned` | One single-threaded loop (`while ($true) {}`) on a machine with eight cores. | 10 min |
| `disk.low_free_space` | Copy a big file onto a small volume you own — a USB stick, not `C:`. | 10 min |
| `disk.filling_fast` | Copy ten gigabytes onto one volume and leave the app open. | 30 min |
| `memory.pressure` | Two hundred browser tabs, or a virtual machine with too much RAM. | 2 min |
| `memory.commit_pressure` | A VM plus a build: commit charge at 90 % of the limit. The hardest one to provoke deliberately, and the one where a pagefile is the tell. | 5 min |
| `process.runaway_cpu` | `ffmpeg` transcoding one file: one process, all cores, ten minutes. | 10 min |
| `process.memory_growth` | A script that allocates 50 MB a minute and never frees it. | 30 min |
| `disk.slow_transfers` | Copy from a failing USB 2.0 stick, or read an almost-dead optical disc. | 10 min |
| `memory.paging` | The `memory.pressure` recipe, plus a disk that is busy at the same time. | 5 min |
| `gpu.vram_pressure` | A game or a render at a resolution the card cannot quite hold. Needs Windows 10 1709 and WDDM 2.0 — not the Windows 7 machine. | 5 min |

Two rows are worth saying out loud. `cpu.one_core_pinned` needs more than two cores,
because the rule stays quiet on any machine already over 50 % busy, and on a
two-core machine that ceiling swallows the case entirely — a known false negative,
and the honest direction to be wrong in. `gpu.vram_pressure` cannot be provoked at
all on the Windows 7 test machine, and the honest demo there is to show the absence
with the reason rather than to hide it.

## What to send back

The output of the four commands, and the first failure if any of them fails. If
`cargo test` fails, the failure's location names the rule; the fixtures are named
after the behaviour they describe (`gpu-just-under-the-line`,
`disk-freed-again-inside-the-window`), so the fixture that broke says what the rule
got wrong before the assertion does.

If `check-fixtures.py` and `cargo test` disagree, send both. That is the one
disagreement this page cannot resolve on its own, and whichever side is wrong, the
other side is written in a file that can be read.
