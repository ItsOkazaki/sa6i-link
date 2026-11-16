# Fallback and test-build handling

> The v8 Arabic build is **experimental**. Keep your previous working version
> as a fallback. It is not a finished translation or a fully tested release.

## What is preserved here

| | |
|---|---|
| Immutable archive | `sa6i/fallback/Sa6i-Link-Windows-Arabic-v8-Reviewed-TEST.zip` — 15,336,199 bytes, SHA-256 `78da55255ee39c31df9064258b550fbb638e47f60b5daff80142a8b29e750cad`, Drive ID `1DuD1SibgqDeKBGPdKx8aVtXdQmPqunaY` |
| Working baseline | `sa6i/baseline/windows-arabic-v8/` — the same ZIP, extracted (its `source/` overlay is the Sa6i implementation) |
| v8 EXE | `Sa6i-Link-Win7-UI-v8.exe`, SHA-256 `f2a7598aa067eb1ed19628e73b8c958d97db3bb8e09c424a6ab14f393e33d19c`, verified against `READ-ME-FIRST.txt` |
| Android test APK | **external only** — Drive ID `1pD5q0r5UiKjOIT0xBBhWNqALevDlI7Rb`, `Sa6i-Link-Android-Arabic-Reviewed-TEST.apk`, 53,278,990 bytes, "rebuilt and signed; not tested on device" |

**Not preserved anywhere in this session:** the previous known-good **v4/v5
Windows files**. They are not in this repository, and a search of the
connected Google Drive found no Sa6i Link source or earlier build other than
the two Arabic test binaries above. Keep the v4/v5 files on your Windows 7 PC;
the v8 notes explicitly say to keep them. If you want them versioned here,
point me at their Drive link or upload them.

## Original install notes (from `READ-ME-FIRST.txt`)

1. Quit the existing app completely from the system tray (closing the window
   may not exit it — check Task Manager). Keep the v4/v5 files. Back up
   preferences and pairings if possible: versions share them.
2. Copy these **four** files into the existing working app folder, beside the
   Qt DLLs and the existing `cldapi.dll`:
   `Sa6i-Link-Win7-UI-v8.exe`, `Start Sa6i Link v8.exe`,
   `sa6i-icon-hook-v4.dll`, `nectarlink_ar.qm`. The icon helper is unchanged
   from v5 — keep the existing one if already present.
3. Copy `translations/qtbase_ar.qm` into the existing `translations` folder
   (create it if needed). Don't overwrite other language files or any system
   DLL; back up an existing `qtbase_ar.qm` first.
4. Enable **VxKex** for `Sa6i-Link-Win7-UI-v8.exe` as with v4/v5, then run
   `Start Sa6i Link v8.exe`.
5. Settings → General → Language → More → العربية. Test the guide, phone
   mirroring and control. Choose **English** in the language row to return.
   To roll back, quit this version and run the old v4/v5 launcher.
6. **Do not use the original updater.** Do not copy packaged DLLs into Windows
   system directories. The temporary Wine-only test dependencies are not
   included and should not be installed on Windows.

## Provenance

This is a private experimental **binary/resource patch** of official
NectarLink 0.1.5 x64, not a source-compiled Sa6i build. Upstream corresponding
source: `https://github.com/thtbee/nectarlink/tree/v0.1.5`. Qt's Arabic base
catalogue is supplied separately under its Qt licensing — see
`baseline/windows-arabic-v8/source/QT-TRANSLATIONS-COPYRIGHT.txt`.

## What "fallback" means for this branch

- The imported `v0.1.5` source tree is the code baseline; `CHANGES.md` lists
  the only edits on top of it, so reverting the Arabic carry-over is a clean
  `git revert`.
- `fallback/*.zip` is never modified — it is the byte-identical Drive archive.
- `baseline/windows-arabic-v8/` is the reference for what the Sa6i version
  actually does; its `source/` scripts are version-locked to the v0.1.5 EXE.
- No APK is committed to Git (the upstream `.gitignore` also excludes
  `*.apk`).
