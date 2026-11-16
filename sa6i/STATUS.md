# Sa6i Link — status

Legend: **done (test build)** = implemented in the Sa6i v8 Windows binary;
**carried into source** = placed into the imported `v0.1.5` tree in this pass;
**open** = still required.

| Area | State | Where | Still needed |
|---|---|---|---|
| Windows 7 x64 compatibility (Wi-Fi pairing, phone mirroring, PC control) | done (test build), user-reported working | `baseline/windows-arabic-v8/source/rebuild_test_patch.py`, `launcher*.c`, `iconhook.c` | Re-verify on the real Windows 7 PC; the sandbox cannot run it. Phone storage through Windows Explorer is **not** supported by the shim. |
| Transparent branding + new font | done (test build) | `source/patch-ui-v3.py`, `patch-ui-v4.py`, `patch-icons.py` | Not ported to source. See the caution in `CHANGES.md` before touching source strings. |
| Arabic under Settings → General → Language | done (test build) + carried into source | v8 binary offers `More → العربية`; `desktop/app/src/i18n.rs`, `desktop/app/i18n/nectarlink_ar.ts` | **Expert human Arabic review.** Machine-generated with curated corrections; some wording, dynamic/system/hard-coded text may stay English. |
| Arabic translation quality checks | done | `ARABIC-CHECK-NOTES.txt`, `source/audit-arabic.py`, `apply-arabic-review.py`, `clarify-arabic.py`, `*.json` | LanguageTool 6.6 + Hunspell/AyaSpell: 3,179 records, 2,568 distinct values, 105 batches, 0 failed; 272 curated overrides / 521 entries, 515 spelling edits, 155 clarity edits, 24 Qt + 42 Android plural forms, 0 placeholder mismatches. Leads, not verified correctness — human review essential. |
| Complete RTL layout | **open** | v8 notes: Arabic is shaped/right-aligned where Qt does it automatically; global layout mirroring was disabled because it caused anchor-loop warnings | Full RTL mirroring (anchors, icons, navigation, mirrored controls) + Windows 7 and phone testing. Not implemented. |
| Local guide uses Sa6i Link content | done (test build) + carried into source | `desktop/app/qml/pages/FeaturesGuidePage.qml` ← `LocalGuide-checked.qml` | Follows `Preferences.language`; the old separate Arabic switch is gone. Verify language switching while the app is open on Windows 7. |
| Android 11 in-app language selection | **open / intentionally unresolved** | `android/app/src/main/kotlin/app/nectarlink/android/ui/AppLanguage.kt` | Upstream `AppLanguage.supported` requires Android 13 (API 33). On Android 11 the app follows the **phone's system language** — which is the stated test intent. `values-ar` + `ar` in `locales_config.xml` mean an Arabic-system OPPO A54 picks Arabic. The in-app picker itself remains unbuilt and untested. |
| Android Arabic strings + plurals | done (test APK) + carried into source | `values-ar/strings.xml` (1,214 strings, 7 plural resources / 42 forms) | Human review; real-device check on the OPPO A54. |
| Performance presets: smoother / balanced / sharper | **not implemented** | `READ-ME-FIRST.txt`: "Performance presets are NOT included" | Design + implement + test. Never started. |
| Window-button fixes (v5 vector caption buttons) | done (test build) | `source/patch-caption-v5.py` | **Windows 7 testing.** Unverified on real hardware; not ported to source. |
| Real-device testing | **open** | — | See checklist below. |
| Browser version / hybrid | **deferred** | `BROWSER-HYBRID.md` | No decision to build. Recorded only. |
| Previous working build as fallback | preserved externally | `FALLBACK.md` | Keep the v4/v5 files on the Windows PC; they are not in this repo or in the connected Drive. |

## Test checklist (needs the real hardware)

Windows 7 x64 PC, with the v8 files installed into the existing app folder and
VxKex enabled:

1. Quit the old app fully from the tray; back up preferences and pairings
   (versions share them). Keep the v4/v5 files untouched.
2. Settings → General → Language → More → العربية: confirm Arabic appears in
   Settings and in the local guide; then switch back to English.
3. Change language **while the app is open** — check every open window
   retranslates, and look for QML warnings/anchor loops.
4. Guide buttons ("Show me", "Learn more", pairing) work in Arabic and English.
5. Wi-Fi pairing, phone mirroring and PC control with the OPPO A54 connected.
6. Caption/window buttons (minimize, maximize, close) in both themes.
7. Confirm no system DLLs were replaced and the original updater is unused.

OPPO A54 / Android 11:

1. Set the **phone system language** to Arabic; confirm the app shows Arabic
   resources (no in-app picker expected on Android 11).
2. Repeat with English; check plurals (0/1/2/few/many/other) and format
   placeholders in notifications.
3. Confirm pairing, mirroring permission prompts and control still work.
4. Do not rely on the Wine-only smoke check from the previous build.

## Known limitations carried over

- The v8 build is a private binary/resource patch of official NectarLink 0.1.5
  x64, not a source-compiled Sa6i build.
- Phone storage in Windows Explorer is unsupported by the compatibility shim;
  PC-to-phone capture is unverified.
- Do not use the original updater; do not copy the packaged DLLs into Windows
  system directories.
- The temporary Wine-only test dependencies are not included and must not be
  installed on Windows.
