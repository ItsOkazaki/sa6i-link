# Release readiness: Sa6i Link with Sa6i Clean in one window

Status as of 2026-11-16. This file separates what has evidence from what does not. It is the authoritative verdict; older notes in `INTEGRATION.md` describe how the work got here.

## Verdict

**Ready to hand out as a release candidate on the tested machine. Not ready to label a final production release.**

The integration behaves as requested on the user's Windows 7 + VxKex system, and the packaged cleaner's JavaScript is now provably the released Cleanly 0.2.0 source plus the documented Sa6i patches. What remains is not more packaging work: it is destructive-action testing on a disposable Windows installation, a decision on the redirected-cleanup-root gap below, and the licensing/signing items.

## What is verified

| Item | Evidence |
| --- | --- |
| Same-window integration, Back/reopen, resize/maximize, faster reopen, standalone candidate launches | User's own reports. This is the only source for these claims; no details of what was exercised were reported. |
| Packaged cleaner JavaScript = public Cleanly v0.2.0 source + documented patches | `verify_upstream_equivalence.py` against commit `b62bef4`; every file matched, including `main.js`, `preload.cjs` and the React bundle. |
| Candidate archive integrity | ZIP SHA-256 `9eff3b026f4c1392222282214b126281ef60e1731b5a26bbdc8bf0138649c935`; component hashes pinned in `package_standalone_candidate.py`; 1,235 entries checked, CRCs pass, classic ZIP (no ZIP64). |
| Cleaner guard behaviour and its one limitation | `tests/probe_upstream_cleanup.mjs`, isolated Linux fixture with Electron stubbed; see `SAFETY-REVIEW.md`. |
| Desktop host is built from this checkout | Windows workflow artifact, desktop SHA-256 `721d78f0…`; the cleaner is the separately packaged upstream app. |
| Unit tests, native and QML simulations, Windows build | Local suites and hosted runs listed in `INTEGRATION.md`; all use synthetic fixtures. |

## What is not verified

- **No cleanup, Recycle Bin emptying, uninstall or startup change has ever been run**, on Windows 7 or anywhere else. Every such action is permanent or system-wide, and the code review found one containment gap.
- **No Windows 10/11 run at all**, and no run by us on Windows 7. Windows 7 also needs VxKex for the cleaner and the bundled `cldapi.dll` shim, which disables Explorer phone-storage integration.
- The 40-pixel header clearance is a visual workaround; the underlying compositor offset is still unexplained.
- The app is unsigned. Windows will show SmartScreen/unknown-publisher warnings, and the Win7 shim and patched binaries make antivirus false positives plausible.
- Redistribution rests on the user's statement that the rights holder gave permission. The upstream repository is marked `UNLICENSED`; no written grant is in this repo. Electron/Chromium notices and the OFL font licences are retained.

## Decision on the redirected-root gap

Cleaning a cache folder whose path passes through a junction/symlink above the folder can delete data outside the intended cache (`SAFETY-REVIEW.md` explains the exact conditions and why the risk is limited on Windows). Fixing it means changing upstream deletion code, re-pinning hashes and re-testing the entire cleaner on Windows. That was deliberately **not** done to the candidate the user has already run, because an unverified change to the deletion path is a worse trade than a documented limitation. The candidate remains the one known to launch on their machine.

If the cleaner is to ship beyond a preview, the next build should canonicalise the cache root (refusing when it resolves elsewhere) and be re-tested; refusing is a safe failure because it only skips cleaning.

## Gates to call this final

1. Cleanup rehearsal on a disposable Windows 7 + VxKex and a Windows 10/11 VM: temp files, browser cache, Trash, old downloads, locked files, junctioned caches, full Recycle Bin, then a restart and a data-integrity check. *(Needs a Windows environment; cannot be done in this sandbox.)*
2. Decide and implement the redirected-root guard, or state the limitation in the installer and in the app. *(Code change plus the test in gate 1.)*
3. Licensing: archive the rights holder's permission, keep notices, and confirm the Qt backport and cleaner redistribution terms. *(User/legal.)*
4. Code signing and an installer/uninstaller that never overwrites the original Sa6i Link. *(Certificate and build infrastructure.)*
5. Fresh-machine smoke test of the signed build, including SmartScreen and antivirus behaviour.

## What to give users today

The existing candidate archive, described as a preview rather than a finished product. No binary changed, so the working folder needs no re-download. Its own `READ FIRST - CANDIDATE.txt` and `Sa6i Clean/SAFETY-REVIEW.md` were written before the user's confirmation and before the source review, so they are stale; the corrected copies are in [Sa6i Clean Candidate Notices.zip](https://drive.google.com/file/d/1Qvoi16TLcq4RTGptUa4DoXJRiL7vRg81/view) (SHA-256 `e0dc2c3a7caa14a719bbddecc40052b12064d81e9cd8244e01a1b5255d860d32`) and can be extracted over the candidate folder.
