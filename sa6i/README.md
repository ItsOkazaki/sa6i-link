# Sa6i Link workspace

Everything specific to the rebrand lives here. The rest of the repository is
upstream NectarLink source at `v0.1.5`.

## Layout

```
sa6i/
├── README.md                     this file
├── STATUS.md                     feature-by-feature state + test checklist
├── CHANGES.md                    the seven source edits carried over from v8
├── FALLBACK.md                   fallback, install notes, external APK
├── BROWSER-HYBRID.md             the browser idea (noted, not built)
├── NOTICE.md                     licences and attribution
├── assets/
│   ├── sa6i-link-logo.png         the logo you supplied (image-1.png)
│   └── Sa6i-Link.ico              icon from the v8 build's source overlay
├── fallback/
│   └── Sa6i-Link-Windows-Arabic-v8-Reviewed-TEST.zip   immutable Drive archive
└── baseline/windows-arabic-v8/    that ZIP, extracted as the working baseline
    ├── READ-ME-FIRST.txt          original install + provenance notes
    ├── ARABIC-CHECK-NOTES.txt     LanguageTool / Hunspell / AyaSpell review notes
    ├── Sa6i-Link-Win7-UI-v8.exe   patched Windows 7 x64 test binary
    ├── Start Sa6i Link v8.exe     launcher (VxKex)
    ├── sa6i-icon-hook-v4.dll      icon helper
    ├── nectarlink_ar.qm           compiled Arabic app catalogue
    ├── translations/qtbase_ar.qm  Qt's Arabic base catalogue
    ├── LICENSE                    package licence file
    └── source/                    the whole Sa6i patch chain + reviewed artefacts
        ├── nectarlink_ar-DRAFT.ts / nectarlink_ar-reviewed.ts
        ├── LocalGuide.qml / LocalGuide-checked.qml
        ├── android-ar/{strings.xml,plurals.xml,locales_config.xml,AppLanguage.smali}
        ├── patch-*.py, launcher*.c, iconhook.c, *.json
        └── GPL-3.0-or-later.txt, MPL-2.0.txt, LGPL-3.0-only.txt,
            CC-BY-4.0.txt, QT-TRANSLATIONS-COPYRIGHT.txt
```

## Provenance

| Item | Value |
|---|---|
| Upstream base | `thtbee/nectarlink` `v0.1.5`, commit `58e530f27726aee19a66746576b0e6c764d4278d` |
| Upstream `main` today | `9e1e6a45d37e88f4d5cb5d4f0e0642bb0d517c69` (2026-11-15) — **not** used |
| Windows archive | Drive `1DuD1SibgqDeKBGPdKx8aVtXdQmPqunaY`, 15,336,199 bytes, SHA-256 `78da55255ee39c31df9064258b550fbb638e47f60b5daff80142a8b29e750cad` |
| v8 EXE | SHA-256 `f2a7598aa067eb1ed19628e73b8c958d97db3bb8e09c424a6ab14f393e33d19c` — matches `READ-ME-FIRST.txt` |
| Android APK | Drive `1pD5q0r5UiKjOIT0xBBhWNqALevDlI7Rb`, 53,278,990 bytes, "rebuilt and signed; not tested on device" — deliberately left external |

**Why v0.1.5, not `main`:** the v8 Windows build is a binary/resource patch of
official NectarLink 0.1.5 x64 (its scripts hard-check that EXE's SHA-256 and
file offsets). Its reviewed Arabic catalogue has **1,876** messages, exactly
matching the `v0.1.5` translation template. `main` has a **2,064**-message
template and nine languages, so moving to `main` would mean regenerating the
catalogue and re-doing ~188 translations. Pinning v0.1.5 keeps the imported
source and the existing Sa6i artefacts aligned.

The `source/` patch scripts are **version-specific binary patches**, not a
source build: they rewrite compressed QML resource blobs and the Rust language
table inside the official v0.1.5 EXE. They are preserved as the authoritative
record of what the Sa6i version actually does.

## What was carried into the source tree

No new features were implemented in this pass. The following already-existing
Sa6i artefacts were placed into upstream paths so a source build can offer the
same Arabic as the v8 binary. Exact diffs and rationale: [`CHANGES.md`](CHANGES.md).

- reviewed desktop catalogue → `desktop/app/i18n/nectarlink_ar.ts`
- checked Sa6i local guide → `desktop/app/qml/pages/FeaturesGuidePage.qml`
- `ar` added to `i18n::LANGUAGES` (Settings → General → Language)
- merged Arabic Android strings + plurals → `android/app/src/main/res/values-ar/strings.xml`
- `ar` added to `locales_config.xml`, `AppLanguage.kt`, `LocalesTest.kt`

Branding, the transparent logo, the new font and the vector window buttons
remain **binary patches** in `source/`; they were not re-implemented in source.
See [`STATUS.md`](STATUS.md).

## What was validated here (and what was not)

This sandbox is Linux with no Rust, Qt or Android toolchain (`cargo`,
`rustfmt`, `java` are absent), so no build, unit test, Windows 7 run or OPPO
A54 test was possible. Static checks that did pass:

- all new/edited XML parses; Arabic `.ts` has 1,876 messages, 0 `unfinished`,
  0 empty translations — equal to the `v0.1.5` template
- `build.rs`'s `offered_languages()` and `scripts/package.ps1`'s regex both see
  `ar`, so `lrelease` will produce `nectarlink_ar.qm` in a source build
- `build.gradle.kts` derives `localeFilters = [en, de, zh-rCN, tr, ar]` from
  `locales_config.xml`, so `values-ar` ships in the APK
- `LocalesTest`'s two invariants hold: `AppLanguage.languages` equals
  `locales_config.xml`, and `values-ar` has all 1,214 strings and all 7 plural
  resources (0 missing)
- the extracted v8 EXE hash matches its own provenance note

Building from source still needs a proper Windows (Qt 6 + Rust) and Android
(Gradle) environment; upstream instructions are in
[`../UPSTREAM-README-v0.1.5.md`](../UPSTREAM-README-v0.1.5.md) → "Building from source".
The Qt base Arabic file `translations/qtbase_ar.qm` from the baseline must be
staged beside/under the app just as the v8 installer notes describe.
