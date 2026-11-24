# Two third-party tools, put to the test

One was adopted and one was not. The reasons are here rather than in a commit
message, because the next person will have the same idea and should not have to
rediscover the same four obstacles.

## shrink-anything — adopted, scan only

[EL4CTEO/shrink-anything](https://github.com/EL4CTEO/shrink-anything) finds code
nothing calls, files nothing names and dependencies nothing uses, and keeps each cut
only if your own tests still pass.

It was run on this repository, and it produced 66 candidates and 47 duplicate
groups. **Nothing was cut**: the condition it sets — a check that passes, with at
least as many tests as before — cannot be met here, because the intel crates have
never been compiled. The scan, the triage of six candidates and the corrections that
followed are in [`DEAD-CODE-SCAN.md`](DEAD-CODE-SCAN.md), and
`.github/workflows/shrink-scan.yml` repeats the scan weekly so the list does not have
to be rediscovered.

## WinAppRunner — evaluated, not adopted

[lrusso/WinAppRunner](https://github.com/lrusso/WinAppRunner) — *"Windows App Runner
using Wine in your Web browser"*. A static page (HTML, JavaScript and an 18.6 MB
`WinAppRunnerSystem.zip`) that takes a ZIP whose name matches the EXE inside it, and
runs that EXE inside [Boxedwine](https://github.com/danoon2/Boxedwine). 35 stars; the
last commit is 2021-12-20.

The proposition was genuinely attractive: let a judge or a user try the Windows build
in a browser tab with nothing installed. "Nothing installed" is the whole problem on
the Windows 7 machine this project is tested on, so it was worth testing rather than
dismissing.

It does not work, for five reasons, and the first is fatal.

**1. Bit width.** Boxedwine runs *"a 32-bit version of Wine"* and *"16/32-bit Windows
programs"* — its words. Every Windows binary this repository ships is 64-bit, read
from the PE header of each rather than inferred from a filename:

| machine | size | file |
| --- | --- | --- |
| `0x8664` | 41.18 MB | `sa6i/baseline/windows-arabic-v8/Sa6i-Link-Win7-UI-v8.exe` |
| `0x8664` | 0.08 MB | `sa6i/baseline/windows-arabic-v8/Start Sa6i Link v8.exe` |
| `0x8664` | 0.08 MB | `sa6i/baseline/windows-arabic-v8/sa6i-icon-hook-v4.dll` |

Three PE files in the whole tree, and not one of them would start. (`file` says the
same thing: `PE32+ executable ... x86-64`.)

**2. What the binary needs besides Windows.** Qt 6 through cxx-qt 0.10, the Qt DLLs
beside it, a `cldapi.dll`, and — on Windows 7 — VxKex enabled for the executable,
because the app calls APIs that OS does not have. That is the package's own
`READ-ME-FIRST.txt` talking, not an inference. An emulated CPU running 32-bit Wine is
not where a Qt 6 application with a compatibility shim holds up; Boxedwine's own
README says the web build *"is still slow, need to implement a JIT"* and that *"games
after the year 2010 have limited success"*.

**3. The privacy claim.** WinAppRunner works by uploading your ZIP to a page. This
project's central promise is that nothing leaves the machine. Demonstrating that
promise by uploading the application to a third-party site inverts it in the most
public way available.

**4. No licence.** The repository has no `LICENSE` file and GitHub reports no licence
for it; Boxedwine beneath it is GPL-2.0. Nothing of WinAppRunner could be
redistributed in a release folder, so even a successful test could not have shipped.

**5. Even success would demonstrate nothing.** The intel half of this product is
about numbers measured on the real machine — PDH performance counters, per-core CPU,
commit charge. Under Wine those are unavailable, so a snapshot taken there would
report `Unknown` for everything the rules need. The demo would show a window and no
measurements, which is the opposite of what the deck claims.

### What was done instead

- [`docs/pitch/deck.html`](../pitch/deck.html) — a self-contained page, no network,
  that a judge can open from a USB stick.
- [`M2-FIXTURES.md`](../plan/M2-FIXTURES.md) — the 34 machine behaviours, tabulated.
- [`M2-VERIFY.md`](../plan/M2-VERIFY.md) — four commands for the machine that can
  actually decide, rather than a fifth browser tab that cannot.

### If a browser demo is ever wanted

The honest artifact would be a **32-bit build of something that measures nothing** —
the `--rules` refusal path, for instance, which reads a file, refuses a bad one and
prints why. It would be a real demonstration of a real behaviour with no number that
Wine could have invented. It is not attempted here because nothing in this repository
compiles yet, and a 32-bit target would need a toolchain that does not exist in the
sandbox either.

## How this was checked

Repository metadata (licence, last push, size, topics) through the GitHub API;
Boxedwine's and WinAppRunner's own READMEs quoted rather than paraphrased; the
repository's file list read directly to confirm there is no `LICENSE`; and the bit
width of the shipped executable read from its PE header with twelve lines of Python
rather than guessed from its name.
