# Sa6i Link

Private, experimental rebrand of [NectarLink](https://github.com/thtbee/nectarlink)
for a **Windows 7 x64 PC** and an **OPPO A54 (Android 11)**. This is not an
official NectarLink build. It keeps NectarLink's UI and uses the supplied Sa6i
Link logo (`sa6i/assets/sa6i-link-logo.png`).

## What is in this repository

| | |
|---|---|
| **Base source** | `thtbee/nectarlink` at tag **`v0.1.5`** (`58e530f27726aee19a66746576b0e6c764d4278d`), imported verbatim except for the seven Arabic carry-over edits listed in [`sa6i/CHANGES.md`](sa6i/CHANGES.md). v0.1.5 is the exact release the existing Sa6i Link test build was patched against. Upstream's own README is kept at [`UPSTREAM-README-v0.1.5.md`](UPSTREAM-README-v0.1.5.md) (its "Building from source" section still applies). |
| **Sa6i workspace** | [`sa6i/`](sa6i/README.md) — logo, the vendored Windows Arabic v8 baseline + immutable fallback archive, status, change log, fallback instructions and licensing notes. |
| **Arabic** | Wired into the source tree (desktop `.ts` catalogue + `LANGUAGES`, Android `values-ar`, `locales_config.xml`, `AppLanguage.kt`) and already offered in the v8 Windows test build under **Settings → General → Language → More → العربية**. Reviewed with LanguageTool 6.6 and Hunspell/AyaSpell, **not yet reviewed by a human Arabic expert**. |

> **This is a test, not a release.** Arabic needs expert human review; complete
> RTL layout is not finished; the Android 11 in-app picker is unresolved (the
> test follows the phone's system language); performance presets
> (smoother / balanced / sharper) are requested but **not implemented**; and
> window-button fixes still need Windows 7 testing. Nothing here has been run
> on the target PC or the OPPO A54. Keep your previous working build as a
> fallback: [`sa6i/FALLBACK.md`](sa6i/FALLBACK.md).

## Start here

- [`sa6i/README.md`](sa6i/README.md) — layout, provenance, what was validated and what was not
- [`sa6i/STATUS.md`](sa6i/STATUS.md) — per-feature state and the remaining test checklist
- [`sa6i/CHANGES.md`](sa6i/CHANGES.md) — exact source edits, and why upstream strings were left alone
- [`sa6i/ANDROID-EMULATOR.md`](sa6i/ANDROID-EMULATOR.md) — can `docker-android` test the APK? Assessment + recipe
- [`sa6i/FALLBACK.md`](sa6i/FALLBACK.md) — the v8 baseline/fallback, install notes and the external APK
- [`sa6i/BROWSER-HYBRID.md`](sa6i/BROWSER-HYBRID.md) — the browser idea, noted but not built
- [`sa6i/NOTICE.md`](sa6i/NOTICE.md) — licenses and attribution
- [`sa6i/CONTINUE.md`](sa6i/CONTINUE.md) / [`sa6i/continue.html`](sa6i/continue.html) — **Continue work** handoff for the next chat

## Not in this repository

- The previous known-good **v4/v5 Windows files** (keep them on your PC — they
  are not here and were not found in the connected Drive).
- The **Android test APK** (53 MB) — it stays external in Drive by design.
- A browser/hybrid build — the idea is recorded only, no decision to build it.
- Any new implementation of presets, full RTL mirroring or a source-level
  rebrand. This pass only carries across work that already exists in the Sa6i
  version.

## Licensing

Upstream is apps GPL-3.0-or-later, core MPL-2.0, docs CC-BY-4.0 (see
[`LICENSE`](LICENSE) and [`LICENSES/`](LICENSES/)). NectarLink's
[`TRADEMARKS.md`](TRADEMARKS.md) requires forks to use their own name and logo,
which the Sa6i Link brand does. Qt's Arabic base catalogue is distributed under
its own licence; see [`sa6i/NOTICE.md`](sa6i/NOTICE.md).
