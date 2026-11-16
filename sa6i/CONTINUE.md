# Continue the Sa6i Link work

Handoff for the next chat/session. Nothing here requires the previous chat's
workspace files — everything needed is in this repository (and the two Google
Drive test binaries).

## One-click continue

Open **`sa6i/continue.html`** (or the live preview page) and click
**Continue work →**. It copies the prompt below to the clipboard; paste it into
a new chat to resume. The same page links straight to this branch on GitHub.
That button sits directly beside a **Merge PR #1** button, which opens PR #1
on GitHub (GitHub's own merge button cannot be changed from the API).

## Prompt to paste

```text
Continue the Sa6i Link private test rebrand on branch `arena/b1010076-sa6i-link` of https://github.com/ItsOkazaki/sa6i-link.

Context: Sa6i Link is a private rebrand of NectarLink (upstream https://github.com/thtbee/nectarlink) for a Windows 7 x64 PC and an OPPO A54 on Android 11. Keep NectarLink's existing UI and use the supplied Sa6i Link logo. The Windows 7 compatibility patch already worked for Wi-Fi pairing, phone mirroring and PC control; transparent branding and a new font also worked. Arabic under Settings → General → Language covers the app and the local guide; it was checked with open-source LanguageTool 6.6 and Hunspell/AyaSpell with selected translations and plurals corrected, but still needs expert human review, complete RTL layout and real-device testing. Android 11 in-app language selection is unresolved — the test is intended to follow the phone's system language. The local guide uses Sa6i Link content. Performance presets (smoother, balanced, sharper) are requested but NOT implemented. Window-button fixes need Windows 7 testing. Keep the previous working v4/v5 build as a fallback. A browser hybrid (native phone + PC services, browser interface) was suggested but I have not decided to build it — do not build it without asking.

Do not assume the previous chat's workspace files are available here: inspect the connected GitHub repository and ask me which repo to use if needed.

In this repo: upstream source is pinned to tag v0.1.5 (the release the Windows Arabic v8 test build patches). `sa6i/` holds the vendored v8 Windows baseline, the immutable fallback ZIP, the supplied logo, STATUS.md, CHANGES.md, FALLBACK.md, NOTICE.md, BROWSER-HYBRID.md and CONTINUE.md. The Android test APK stays external in Google Drive (file ID 1pD5q0r5UiKjOIT0xBBhWNqALevDlI7Rb); the Windows ZIP is 1DuD1SibgqDeKBGPdKx8aVtXdQmPqunaY. Branding/font/window-button changes exist only as version-locked binary patches in sa6i/baseline/windows-arabic-v8/source/ — do not rebrand upstream source strings without regenerating the Arabic catalogue.

An emulator (HQarroum/docker-android) was assessed as a possible way to test the Android APK; see sa6i/ANDROID-EMULATOR.md. It can smoke-test the APK and the Android 11 system-language path, but the APK's core native library exists only for ARM while docker-android is x86_64, so ARM64 translation (or an x86_64 rebuild) is needed first, and OPPO A54 real-device testing remains required. Read sa6i/STATUS.md and sa6i/CHANGES.md first, then ask me which open item to tackle next: (1) expert Arabic review + complete RTL layout, (2) Windows 7 window-button testing, (3) OPPO A54 / Android 11 real-device test, (4) performance presets, (5) source-level rebrand + catalogue regeneration, or (6) something else. No Rust, Qt or Android toolchain and no Windows 7 PC or OPPO A54 exist in the sandbox, so flag anything that cannot be verified here rather than claiming it was tested.
```

## Current state at handoff

- Branch: `arena/b1010076-sa6i-link` (pushed to `origin`)
- Base: `thtbee/nectarlink` `v0.1.5` (`58e530f27726aee19a66746576b0e6c764d4278d`)
- Arabic carried over into source: reviewed `.ts` (1,876 messages, 0 unfinished),
  `LANGUAGES += ar`, Sa6i local guide, Android `values-ar` (1,214 strings + 7
  plurals), `locales_config.xml`, `AppLanguage.kt`, `LocalesTest.kt`
- Static checks only; no build, no Windows 7 run, no OPPO A54 test
- Open: human Arabic review, full RTL, device tests, presets, window-button
  testing, source-level rebrand; browser hybrid undecided

See [`STATUS.md`](STATUS.md) for the full table and test checklist, and
[`FALLBACK.md`](FALLBACK.md) for the fallback files.
