# Verifying M1 on the machine it is for

Nothing in M1 has been through `rustc`, and the Monitor page has never been
rendered. That is not a disclaimer at the bottom of the report; it is the state of
the milestone. The six exit criteria in
[`M1-REPORT.md`](M1-REPORT.md#where-m1-stands-against-its-exit-criteria) are the
gate in front of M2, and four of them can only be closed on a real PC.

This page is the operator's side of that: two commands, what each one answers, and
what to do when one of them says no.

## Before the first run: a toolchain

The first machine this was tried on had no Rust at all, which is easy to forget when
the whole milestone was written in a sandbox that had none either. From a fresh
Windows terminal:

```powershell
winget install --id Rustlang.Rustup -e
```

Then open a **new** terminal - the installer changes `PATH`, and the one you were
in will not see it - and check:

```powershell
rustup show          # picks up rust-toolchain.toml: stable, rustfmt, clippy
cargo --version
```

Two things will bite if the machine is bare:

- **`link.exe` not found.** rustup's default host on Windows is the MSVC toolchain,
  which needs the Visual Studio C++ build tools, not just rustup. If the build stops
  with a linker error, install them:
  `winget install --id Microsoft.VisualStudio.2022.BuildTools --override "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"`.
  A machine with a Qt/MSVC kit already has them.
- **The first build is slow.** `Cargo.lock` pins 527 packages and none of them are
  compiled yet; several minutes of `Compiling` and a lot of network is normal.

No Qt is needed for `verify-m1.ps1` - it builds `sa6i-link-cli` only. `check.ps1`
does need Qt for the desktop crates.

**And check the Windows version before any of this**, because a toolchain that
cannot start looks exactly like a broken project:

```powershell
[System.Environment]::OSVersion.VersionString
(Get-WmiObject Win32_OperatingSystem).Version
```

rustc 1.78 and later require **Windows 10**. On Windows 7 or 8.1 the build exits
with `-1073741511`, which is `0xC0000139 STATUS_ENTRYPOINT_NOT_FOUND`: the loader
could not resolve a DLL, so `cargo.exe` never ran a line of anything. `cargo
--version` prints nothing at all in that case, which is the tell - a compiler that
has a complaint still prints a version first. The script now says this in the
machine section and translates the code in the build row, so the record carries the
reason instead of a decimal.

## The commands

```powershell
./scripts/check.ps1                # formatting, clippy, every test, headers, deps
./scripts/verify-m1.ps1            # M1's six criteria, and a record to paste back
./scripts/verify-m1.ps1 -Budget    # the same, plus the half hour at 1 Hz
```

`check.ps1` already existed and is the unfiltered answer to *what is broken*. It
runs the whole workspace, the QML tests and the dependency policy. Run it first:
if it fails, nothing below matters yet, and its output is more useful than a
criterion table.

`verify-m1.ps1` answers M1's own question. It builds `sa6i-link-cli`, takes a
minute of samples and asks you for Task Manager's two numbers, checks the JSON
contract with a two-sample run (a rate needs two samples, so one is not enough to
prove the process column works), runs `tests/privacy.rs`, and — with `-Budget` —
takes the half-hour run and reads its exit code. It does not re-run the unit
tests; `check.ps1` did that.

Both write to the console and the second writes
`target/m1-verification.md`: the machine, the numbers, and a row per criterion.

## Who answers what

| Exit criterion | Answered by | If it says no, look at |
| --- | --- | --- |
| Numbers within ±3 % of Task Manager | you, reading Task Manager while the minute runs; the script does the arithmetic | `summary.rs` for the averaging, `intel-win` for the counters, and the slice sections for which counter each number comes from |
| 1 Hz for 30 min under budget | the script, `-Budget`, from the CLI's exit code 3 | `budget.rs` for the limits; if the cost is over, the report's per-sample mean says whether it is the collectors or the loop |
| Win7 renders `Unsupported`, with reasons | the old machine | `WhyUnknown` and the `cfg(not(windows))` collector; nothing else should be involved |
| CLI JSON stable and tested | the script (keys, states, and a rate that is a number or absent) | `model.rs` serde attributes, `view.rs` for the page's contract |
| No admin prompt anywhere | you, watching for a UAC shield | if one appears, a call in `intel-win` needs a privilege it should not have |
| Nothing leaves the machine | the script (`tests/privacy.rs`) | the dependency graph test, and the crate that pulled the crate in |

Two of the six rows above say *you*. That is not the script being lazy: a UAC
prompt is a thing a person sees, and Windows 7 is a thing this workstation is not.

## What "within 3 %" means, exactly

Task Manager's Performance tab shows a live figure; our number is a one-minute
mean. Compare like with like: read the Utilisation and Memory numbers at the end
of the run, on a machine doing roughly the same thing throughout. If the machine
was busy with something else for half the minute, run it again on a quiet one
before believing a miss.

A miss by more than three points is a real finding and not a rounding argument. It
is one of two things, in this order:

1. **The interval slipped.** The `-Budget` run answers this directly: if the rate
   is below 1 Hz, the numbers above were averaged over a longer window than Task
   Manager's and will read low on CPU.
2. **The counter is read differently.** The slice sections in `M1-REPORT.md` name
   the call behind each number — `GetSystemTimes` for CPU, `GlobalMemoryStatusEx`
   for memory, `PdhGetFormattedCounterArrayW` for disk and GPU — so the
   comparison can be made against the same figure in Task Manager's own tooltip,
   and the disagreement located in one function.

## What to send back

`target/m1-verification.md` — plus `check.ps1`'s output if it failed. The first
failure is the one to fix; the report's per-slice sections say which file owns
each of them, and the whole point of keeping the slices small is that none of
them is a rewrite.

## If you would rather not read a table

`sa6i-link intel snapshot --json --budget` exits 3 when the sampler misses its
budget and puts the verdict inside the same JSON document as the snapshot, so a
CI job can assert on one file and one exit code without parsing the block of text
a person reads.
