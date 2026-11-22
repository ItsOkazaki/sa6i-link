# Cleanly 0.2.0 cleanup review

This review covers the cleaner that ships inside the Sa6i Link candidate: Cleanly 0.2.0 by 0xCodez. The packaged JavaScript is now traceable to that project's public source; cleanup itself has **not** been executed on Windows, so this remains a code-level review, not a safety certification.

## Provenance (verified 2026-11-16)

- Source: `0xCodez/cleanly`, tag `v0.2.0`, commit `b62bef4d4478cd8d570dcdc537eaddb61ae53eeb` (released 2026-11-03). No newer tag exists.
- The candidate's `resources/app.asar` was extracted and compared with a local production build of that source (`npx vite build`, `node scripts/build-electron.mjs`) plus the Sa6i patches listed below.
- Result: **every packaged file matched byte for byte**, including `dist-electron/main.js` (`23fa9683…`), `preload.cjs` (`189044c8…`) and the React bundle (`2af83342…`). Only `package.json` (pruned fields) and `dist/index.html` (one blank line) differ, both checked by content.
- Reproduce with `python3 sa6i/clean/verify_upstream_equivalence.py SOURCE EXTRACTED_ASAR --build`. Builds are reproducible here despite `^` dependency ranges, but that is an observation, not a guarantee for other toolchain versions.
- The executable itself is the upstream Electron 45 binary, not a source build: only its PE icon resources and the embedded ASAR integrity hash changed. Its Windows metadata and signature state are unchanged (unsigned).
- Sa6i patches applied to the source build: window title, frameless window options, removal of the native title-bar overlay update, dark/light theme default from a host command-line switch, Sa6i theme stylesheet and fonts, logo replacement, and the warning/attribution strings on the Cleanup, Feedback and Support screens.

What this does **not** establish: that the reviewed behaviour is safe, that Windows 7 runs it fully, or that the rights holder's permission covers redistribution in this form. The repository declares `"license": "UNLICENSED"`.

## How cleaning works (reviewed code)

- Ordinary cache categories (`Temporary files`, `Windows temp`, `Browser caches`, `Thumbnails`, shader caches, and the macOS/Linux equivalents) call `deleteCacheEntry`, which **permanently deletes** files with `fs.unlink` and removes emptied folders with `fs.rmdir`. There is no Recycle Bin step and no undo. Entries with a day-old modification/creation time are kept for temp categories.
- The list of locations is derived inside the main process from category IDs (`cleanJunk` only accepts IDs), so the renderer cannot ask for an arbitrary path to be deleted. This meaningfully limits the impact of a compromised renderer.
- `Trash` and `Old downloads` use Electron `shell.trashItem`, which moves items to the Recycle Bin. Old downloads are limited to files in Downloads untouched for 90 days and filtered through `isSafeUserPath` (home-only, no protected folders, no key stores, no symlinked targets, canonical path re-checked after `realpath`).
- Emptying the Recycle Bin runs `Clear-RecycleBin -Force -ErrorAction SilentlyContinue` through Windows PowerShell. It is permanent and errors are suppressed; availability on Windows 7 with VxKex is untested.
- Other sections (startup items, app uninstall, disk usage, duplicates, AI) are outside this review and untested.

## Limitation found: a redirected cache root is not re-validated

`deleteCacheEntry(target, root)` guards the **target**: it rejects a direct symlink/junction target and re-checks containment after `realpath`. It never canonicalises `root`, and the root is only checked by `isRealDir`, which uses `lstat` on the root path itself. So if a redirect sits *above* a cache root, the root looks like an ordinary directory and its contents are deleted through the redirect.

`sa6i/clean/tests/probe_upstream_cleanup.mjs` demonstrates this against the pinned source in an isolated Linux fixture, with Electron and drive enumeration stubbed out and only synthetic files inside one temporary directory:

```
linkTargetRefused: true
redirectedRootAcceptedAsRealDirectory: true
deletedThroughRedirectedAncestor: true
```

Measured on a disposable Windows runner (workflow `Sa6i Clean Windows cleanup probe`, run `45033090483`, Windows Server image, real NTFS, synthetic files only):

```
junctionReportedAsLinkByLstat          true    -> a junction target IS refused (sentinel survived)
redirectedRootLooksLikeDirectory       true
deletedThroughRedirectedRoot           true    -> a junction ABOVE the root is followed
siblingOutsideCacheSurvived            true    -> deletion stays inside the redirected subtree
plainCacheRemoved / rootEmptied        true
guardAllowsWindowsSystem/Desktop/.ssh  false   -> protected paths blocked
guardAllowsOrdinaryUserFile            true
guardAllowsRelativePath                false
```

So on Windows the exposure is narrower than a naive reading suggests: a cache root that *is* a junction is refused, and only a junction above it defeats the check. Relocating a profile or `%TEMP%` with a junction is a common disk-space workaround, so such configurations exist; the usual result is still deleting inside the intended cache, but a redirect aimed at unrelated data that happens to contain cache-named folders would have that data deleted. Re-run with `.github/workflows/sa6i-clean-windows-cleanup-probe.yml`.

Mitigations available today: tell users not to clean on a machine that uses junctions to relocate these folders, or ship a guard. A guard would have to refuse or canonicalise redirected roots; that means changing upstream code and re-testing the whole cleaner, which this candidate does not do.

## Hardened build (2026-11-22)

The rebuilt candidate refuses a cache root whose own path, or any folder above it, is a junction or symlink. `isUnredirectedRoot` in the guarded `trash.ts` walks every path component with `lstat` once per root and caches the verdict; `deleteCacheEntry` then returns `refused` without deleting. Refusing only skips that category, so the failure mode is "nothing cleaned" rather than "deleted elsewhere".

Why the guard inspects components instead of comparing canonical paths: the first attempt compared `realpath(root)` with the requested spelling and the Windows runner refused ordinary cleaning, because `os.tmpdir()` there is the 8.3 short path `C:\Users\RUNNER~1\...` while `realpath` returns `runneradmin`. Letter case and 8.3 spellings now pass; only real links are refused.

Verified on the disposable Windows runner (`Sa6i Clean Windows cleanup probe`, run `45034853645`):

```
junctionTargetRefused          true   junctionTargetSentinelSurvived  true
guardAcceptsPlainRoot          true   plainCacheRemoved               true
guardAcceptsUpperCasedRoot     true   uppercasedRootCleaned           true
guardRejectsRedirectedRoot     true   redirectedDeletionRefused       true
redirectedSentinelSurvived     true   siblingOutsideCacheSurvived     true
```

The guarded source (SHA-256 `a768fff4…`) and the guarded packaged bundle come from the same text: `guard_snippet.js` is inserted verbatim by `harden_cleaner.py`, unit-tested by `tests/test_guard_snippet.mjs`, and `verify_upstream_equivalence.py --guard` reproduces the shipped ASAR byte for byte from the public source. The desktop executable's two compiled-in cleaner digests were replaced in place; it differs from the tested build in exactly those 64 bytes.

Still not safety evidence: the guard has never run inside the real application, and no cleanup, Recycle Bin, uninstall or startup action has been executed anywhere.

## This candidate's changes

Branding, window chrome, theme default and warning text only. The deletion implementation, categories, default selections and confirmation behaviour are unchanged. The confirmation option can still be switched off in settings, and the Smart Scan can clean from the dashboard, so the labels `safe` and the warnings are not guarantees.

## Before any production release

- Run cleanup on disposable Windows 7 + VxKex and Windows 10/11 systems with synthetic files and verified backups, covering locked files, junctions, long paths and a full Recycle Bin.
- Re-test the guard inside the real app (a redirected cache folder should be reported as blocked, an ordinary one should clean normally).
- Confirm redistribution permission in writing and keep the Electron/Chromium notices and the bundled font licences.
- Obtain code signing and an installer that preserves the user's existing installation.
