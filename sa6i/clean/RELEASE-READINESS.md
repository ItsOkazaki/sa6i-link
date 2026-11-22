# Release readiness: Sa6i Link with Sa6i Clean in one window

Status as of the latest build. This file separates what has evidence from what does not. It is the authoritative verdict; older notes in `INTEGRATION.md` describe how the work got here.

## Verdict

**A hardened release candidate is ready to test on the Windows 7 machine. Not ready to label a final production release.**

The integration behaves as requested on the user's Windows 7 + VxKex system, the packaged cleaner's JavaScript is provably the released Cleanly 0.2.0 source plus the documented Sa6i patches, and the redirected-cleanup-root gap is now guarded. What remains is not more packaging work: it is destructive-action testing on a disposable Windows installation, confirming the guard inside the real app, and the licensing/signing items.

## What is verified

| Item | Evidence |
| --- | --- |
| Same-window integration, Back/reopen, resize/maximize, faster reopen, standalone candidate launches | User's own reports. This is the only source for these claims; no details of what was exercised were reported. |
| Packaged cleaner JavaScript = public Cleanly v0.2.0 source + documented patches | `verify_upstream_equivalence.py` against commit `b62bef4`; every file matched, including `main.js`, `preload.cjs` and the React bundle. |
| Candidate archive integrity | ZIP SHA-256 `9eff3b026f4c1392222282214b126281ef60e1731b5a26bbdc8bf0138649c935`; component hashes pinned in `package_standalone_candidate.py`; 1,235 entries checked, CRCs pass, classic ZIP (no ZIP64). |
| Cleaner guard behaviour | Unpatched upstream followed a junction above a cache root on real NTFS (run `45033090483`). The guarded build refuses it and still cleans ordinary folders, including 8.3 and differently cased spellings (run `45034853645`). |
| Desktop host is built from this checkout | Windows workflow artifact, desktop SHA-256 `721d78f0…`; the cleaner is the separately packaged upstream app. |
| Unit tests, native and QML simulations, Windows build | Local suites and hosted runs listed in `INTEGRATION.md`; all use synthetic fixtures. |

## What is not verified

- **No cleanup, Recycle Bin emptying, uninstall or startup change has ever been run**, on Windows 7 or anywhere else. Every such action is permanent or system-wide, and the earlier build had a containment gap that the hardened build now guards.
- **No Windows 10/11 desktop run and no Windows 7 run by us.** Deletion functions were exercised on a GitHub Windows Server runner with synthetic files, which is evidence about NTFS behaviour, not about the app's interface, Electron rendering, the Recycle Bin shell integration, or Windows 7. Windows 7 also needs VxKex for the cleaner and the bundled `cldapi.dll` shim, which disables Explorer phone-storage integration.
- The 40-pixel header clearance is a visual workaround; the underlying compositor offset is still unexplained.
- The app is unsigned. Windows will show SmartScreen/unknown-publisher warnings, and the Win7 shim and patched binaries make antivirus false positives plausible.
- Redistribution rests on the user's statement that the rights holder gave permission. The upstream repository is marked `UNLICENSED`; no written grant is in this repo. Electron/Chromium notices and the OFL font licences are retained.

## Hardened build

[Part 1](https://drive.google.com/file/d/1Cz8T4lliKrjUAFfBHTquxWs0BpUFNpPj/view) · [Part 2](https://drive.google.com/file/d/1kk6l5A4gbFUA-QmvFeA6qTHjBN9QGxBJ/view). Join, then verify SHA-256 `b8b03563662a9321d28d36f946ec26899a6475418fc8d20014d12a696930025d` before extracting.

```bat
copy /b "Sa6i Link Hardened Candidate.zip.000"+"Sa6i Link Hardened Candidate.zip.001" "Sa6i Link Hardened Candidate.zip"
```

Part MD5s: `4be24f2137e5fba423c4e3cf7c40f3c4` and `04d44835b15d0f92d4d216a107642f9f`. Extract to a new folder and run `Start Sa6i Link Candidate.cmd`.

What differs from the tested candidate, entry by entry: the cleaner executable (`2c9bdd29…`, only its embedded ASAR digest changed), its ASAR (`4cbe981c…`, source plus branding plus guard), the desktop executable (`5b8920ae…`, only its two compiled-in cleaner digests changed), the read-first/notice/safety text, and one added `SA6I-HARDENING.md`. All 1,235 original entries are otherwise byte-identical and CRCs pass. The archive is a classic ZIP with no ZIP64.

The guarded ASAR was reproduced byte for byte from the public source plus the documented patches (`verify_upstream_equivalence.py --guard`), so the shipped cleaner code is fully accounted for.

## Decision on the redirected-root gap

The hardened build refuses any cache root reached through a junction or symlink above it, verified on a disposable Windows runner with synthetic files. The refusal is a safe failure: that category is skipped and reported as blocked for safety. What is **not** yet proven is that the guard behaves the same inside the real Electron app, and that ordinary cleaning still works there. That is a five-minute check in the release rehearsal below, not a code question.

## Gates to call this final

1. Cleanup rehearsal on a disposable Windows 7 + VxKex and a Windows 10/11 VM: temp files, browser cache, Trash, old downloads, locked files, junctioned caches, full Recycle Bin, then a restart and a data-integrity check. *(Needs a Windows environment; cannot be done in this sandbox.)*
2. Confirm inside the real app that a redirected cache folder is reported as blocked and an ordinary one cleans. *(Covered by gate 1; the guard itself is already built and runner-tested.)*
3. Licensing: archive the rights holder's permission, keep notices, and confirm the Qt backport and cleaner redistribution terms. *(User/legal.)*
4. Code signing and an installer/uninstaller that never overwrites the original Sa6i Link. *(Certificate and build infrastructure.)*
5. Fresh-machine smoke test of the signed build, including SmartScreen and antivirus behaviour.

## What to give users today

The hardened build above, described as a test build. Keep the earlier candidate folder as the fallback, since it is the only build observed to launch on the user's machine. If only the earlier candidate is wanted, it still works, and its stale notices can be refreshed with [Sa6i Clean Candidate Notices.zip](https://drive.google.com/file/d/1Qvoi16TLcq4RTGptUa4DoXJRiL7vRg81/view).
