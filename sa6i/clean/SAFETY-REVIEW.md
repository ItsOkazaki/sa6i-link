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

Scope and likelihood on Windows are limited:

- Node's `lstat` reports a junction itself as a link, so a cache root that **is** a junction is refused. Only a junction *above* the root defeats the check.
- Relocating a browser profile or `%TEMP%` with a directory junction is a common disk-space workaround, so some users do have such redirects; the usual outcome is still deleting inside the intended cache, but if the redirect points at unrelated data with cache-like subfolder names, that data can be deleted.
- Windows junction behaviour was **not** tested here. The Linux result establishes the class of gap, not a Windows exploit.

Mitigations available today: tell users not to clean on a machine that uses junctions to relocate these folders, or ship a guard. A guard would have to refuse or canonicalise redirected roots; that means changing upstream code and re-testing the whole cleaner, which this candidate does not do.

## This candidate's changes

Branding, window chrome, theme default and warning text only. The deletion implementation, categories, default selections and confirmation behaviour are unchanged. The confirmation option can still be switched off in settings, and the Smart Scan can clean from the dashboard, so the labels `safe` and the warnings are not guarantees.

## Before any production release

- Run cleanup on disposable Windows 7 + VxKex and Windows 10/11 systems with synthetic files and verified backups, covering locked files, junctions, long paths and a full Recycle Bin.
- Decide the redirected-root question above and record the answer in the release notes.
- Confirm redistribution permission in writing and keep the Electron/Chromium notices and the bundled font licences.
- Obtain code signing and an installer that preserves the user's existing installation.
