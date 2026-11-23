# Windows 7: what is kept, and what cannot be

Decided after the first real machine turned out to be Windows 7 SP1
(`6.1.7601`, PowerShell 2.0) and could not build anything: rustc 1.78 and later
raise the minimum to Windows 10, so `cargo` exits `0xC0000139` there without
printing a version.

The answer chosen was **keep Windows 7, via the nightly `win7` target**. This page
is what that decision actually buys, because it is less than the word "support"
suggests and more than dropping it.

## The split: the collector can, the window cannot

| piece | Windows 7 possible? | why |
| --- | --- | --- |
| `sa6i-link-cli`, `sa6i-link-intel-win` | **yes**, built for `x86_64-win7-windows-msvc` | pure Rust plus Win32 calls that exist in `kernel32`/`pdh` on Windows 7 |
| the Qt desktop app | **no** | Qt 6 supports Windows 10 1809 and later only, and cxx-qt 0.10 generates Qt 6 code. There is no Qt 6 build that runs on Windows 7, and no cxx-qt build that emits Qt 5 |

That is not a policy this project can negotiate: it is two upstream floors, and
the second one (Qt) is higher than the first (Rust). So criterion 3 is reworded to
the half that can be kept:

> **Old:** Win7 renders `Unsupported`, with reasons.
>
> **Now:** on Windows 7, the CLI reports every metric it cannot read as `Unknown`
> with a reason, and exits successfully. The desktop app requires Windows 10 1809
> and says so in its installer rather than failing to start.

The criterion's *point* survives the rewording: nothing is invented on a machine
that cannot be measured, and the unmeasured part says why. What changes is that it
is demonstrated with `sa6i-link intel snapshot` on that machine rather than with a
window that will not open.

## The build, exactly

On a Windows 10/11 machine, from the repository root:

```powershell
rustup toolchain install nightly --profile minimal --component rust-src
cargo +nightly -Z build-std=std,panic_abort --target x86_64-win7-windows-msvc `
    -C target-feature=+crt-static --release -p sa6i-link-cli
```

Then copy `target\x86_64-win7-windows-msvc\release\sa6i-link.exe` to the Windows 7
machine and run `sa6i-link intel snapshot`.

Four details, each of which is a way this fails without the line above:

- **`--component rust-src`** is what `build-std` compiles. The target is Tier 3:
  there is no `rust-std` binary for it, so std is built from source in your
  checkout, which is also why the first build takes several minutes.
- **`+crt-static`** removes the dependency on the Universal CRT, which Windows 7
  does not have until `KB2999226` is installed. Without it the exe fails to start
  on a machine that has never run the Windows Update for it - the same
  `STATUS_ENTRYPOINT_NOT_FOUND` class of failure as the toolchain saw.
- **Nightly is invoked, not pinned.** `rust-toolchain.toml` stays on stable, so
  `cargo build`, CI and `scripts/check.ps1` are unchanged; the Win7 build is an
  explicit `+nightly` command with `-Z` flags that stable would reject.
- **Nothing about this is tested upstream.** Tier 3 means the Rust project does
  not build or test these targets; a compile error here is ours to diagnose. That
  is the price of the decision, and it is why the gate below matters.

## What the Win7 build will show, and why it is worth it

Per counter, from `docs/plan/M1-REPORT.md` and the collector's own checks:

- `\GPU Adapter Memory(*)\Dedicated Usage` is Windows 10 1709+ → on Windows 7 the
  GPU section is `Unknown` with the reason `counter missing`, which is criterion 3
  doing its job rather than a failure.
- Commit charge, disk free space, per-process working set, CPU times and uptime all
  exist on Windows 7 and should read normally.
- `Avg. Disk sec/Transfer` (M2's `disk.slow_transfers`) also exists on Windows 7.

So the Win7 run is not a curiosity: it is the cheapest test of the *Unknown*
plumbing that M2's rules depend on, on a machine that cannot fake it.

## Honest state of this page

None of the above has been run. It is a recipe written from documentation by
someone who cannot execute either step: the build needs Windows 10+, and the run
needs the Windows 7 machine, which is the one machine we have. Until both happen,
this page is a plan and criterion 3 is open.

## What would make us revisit it

- The link step fails on api-set import libraries, i.e. the `windows` crate's 0.62
  bindings pull in a function Windows 7 never had at the version we call. The fix
  is per-call, not per-crate: the collector already wraps unreadable metrics.
- The exe starts but `pdh.dll` cannot build the query on Windows 7. Then the Win7
  answer is the same as the iGPU answer: `Unknown`, with the reason, never a zero.
