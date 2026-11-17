# Source changes

The seven changes below were carried over from artefacts in
`baseline/windows-arabic-v8/source/`. Additional desktop labels and Android
strings now use Sa6i Link in source builds. Desktop labels retain their original
translation keys and replace the visible name after translation; installer,
updater and some platform labels still use the upstream name. These later
source changes are not part of the downloadable v8 binary.

| # | File | Change | Source artefact |
|---|---|---|---|
| 1 | `desktop/app/i18n/nectarlink_ar.ts` | **new** — 1,876-message reviewed Arabic Qt catalogue, 0 unfinished, 0 empty | `source/nectarlink_ar-reviewed.ts` |
| 2 | `desktop/app/src/i18n.rs` | `LANGUAGES` gains `("ar", "العربية")`; test asserts `is_known("ar")` | `source/patch-v6-arabic-test.py` (binary patch of the Rust language table) |
| 3 | `desktop/app/qml/pages/FeaturesGuidePage.qml` | **replaced** by the Sa6i Link local guide; follows `Preferences.language`, no separate Arabic switch | `source/LocalGuide-checked.qml` (the reviewed variant, via `patch-guide-reviewed.py`) |
| 4 | `android/app/src/main/res/values-ar/strings.xml` | **new** — merged 1,214 strings + 7 plural resources (42 forms) into one file | `source/android-ar/strings.xml` + `source/android-ar/plurals.xml` |
| 5 | `android/app/src/main/res/xml/locales_config.xml` | added `<locale android:name="ar" />` | `source/android-ar/locales_config.xml` |
| 6 | `android/app/src/main/kotlin/app/nectarlink/android/ui/AppLanguage.kt` | added `"ar" to "العربية"` and `ar`/`ar-*` normalisation | `source/android-ar/AppLanguage.smali` (patched APK) |
| 7 | `android/app/src/test/kotlin/app/nectarlink/android/ui/LocalesTest.kt` | added `normalize("ar")`, `normalize("ar-EG")` assertions | — |

## Why each one is enough

- `desktop/app/build.rs` (`offered_languages()`) and `scripts/package.ps1`
  parse `i18n::LANGUAGES` out of `i18n.rs`, so adding `ar` automatically makes
  `lrelease` compile `nectarlink_ar.qm` for source and installer builds.
  `app_helpers.cpp` loads `nectarlink_<locale>.qm` plus `qtbase_<locale>.qm`
  from `translations/`, which the v8 baseline supplies.
- The reviewed catalogue has no `type="unfinished"` entries. The source build
  and its tests still need to be run in a suitable build environment.
- `MainWindow.qml` guards its page wiring with `("deviceId" in item)` and
  `if (item.<signal>)` checks, so the simpler Sa6i guide (which has
  `pairRequested`, `showMeRequested`, `restartWalkthroughRequested`) loads
  safely. It deliberately replaces upstream's searchable features guide, as
  the v8 binary patch did.
- `android/app/build.gradle.kts` derives `localeFilters` from
  `locales_config.xml`, so `values-ar` is included in the APK. `LocalesTest`
  only looks inside `strings.xml` for plurals, which is why `plurals.xml` was
  merged into that file rather than copied alongside it.
- `AppLanguage.supported` still requires Android 13 (API 33). On the Android 11
  OPPO A54 the app therefore follows the phone's system language, with Arabic
  resources available — exactly the stated test intent. The in-app picker
  remains unresolved and is **not** claimed to work.

## ⚠️ Do not rebrand the source strings casually

Qt looks translations up by the **English source text**. The reviewed
`nectarlink_ar.ts` is keyed to `v0.1.5`'s original `qsTr("NectarLink …")`
strings. Replacing those source strings with `"Sa6i Link …"` (as
`rebuild_test_patch.py` does inside the compiled EXE) would silently orphan
every Arabic translation whose source contains the old brand name.

So the imported source still contains upstream's English text, and the Sa6i
branding lives in the v8 binary patch chain. A source-level rebrand is a
separate task: rebrand first, then regenerate the template with
`cargo xtask strings` / `lupdate`, re-map all 1,876 translations (including the
`NectarLink` ones), and re-run the Arabic checks. Changing `app_name` in
Android resources is safe (keys are resource names, not text) — the Arabic
`values-ar` already uses `Sa6i Link` there.

## Binary-only Sa6i work, preserved but not ported

`baseline/windows-arabic-v8/source/patch-*.py` are version-locked to the exact
official v0.1.5 x64 EXE (hard-coded SHA-256 checks and resource offsets):

- `rebuild_test_patch.py` — Windows 7 loader shims, `NectarLink` → `Sa6i Link`
  in visible `qsTr()` strings, logo/welcome images
- `patch-ui-v3.py` / `patch-ui-v4.py` — "Sa6i Link" title, transparent mark,
  new monospace font
- `patch-icons.py` / `patch-caption-v5.py` — icon payloads, vector caption
  buttons
- `patch-guide-v6.py`, `patch-guide-language.py`, `patch-guide-reviewed.py`,
  `patch-v6-arabic-test.py` — local guide and Arabic language-table patch
- `launcher*.c`, `iconhook.c`, `icon.rc` — launcher and icon helper sources

Porting these to source QML/Rust is a build-and-test task for a Windows/Qt
machine; it was intentionally not attempted here.

## Static validation performed

```
XML parse:              nectarlink_ar.ts, values-ar/strings.xml, locales_config.xml  OK
Catalogue:              1876 messages, 0 unfinished, 0 empty; v0.1.5 template = 1876
build.rs parser:        ['en','de','zh_CN','tr','ar']  (ar present)
package.ps1 regex:      ['en','de','zh_CN','tr','ar']  (ar present)
Gradle localeFilters:   ['en','de','zh-rCN','tr','ar']
AppLanguage.languages:  ['en','de','zh-CN','tr','ar'] == locales_config.xml
LocalesTest invariants: 0 missing strings, 0 missing plurals
v8 EXE SHA-256:         f2a7598a…19c == READ-ME-FIRST.txt
```

These are static checks only — not a source build or a runtime test.
