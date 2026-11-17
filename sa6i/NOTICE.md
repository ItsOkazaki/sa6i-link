# Licences and attribution

Sa6i Link is a private test rebrand of **NectarLink 0.1.5**, originally created by thtbee. This is not an official NectarLink build.

| Part | Licence | Where |
|---|---|---|
| Desktop app (`desktop/`), Android app (`android/`), CLI | GPL-3.0-or-later, with the app-store exception | [`LICENSE`](../LICENSE), [`LICENSES/GPL-3.0-or-later.txt`](../LICENSES/GPL-3.0-or-later.txt), [`LICENSES/APP-STORE-EXCEPTION.md`](../LICENSES/APP-STORE-EXCEPTION.md) |
| Core libraries (`core/`, except CLI) | MPL-2.0 | [`LICENSES/MPL-2.0.txt`](../LICENSES/MPL-2.0.txt) |
| Protocol specification and `docs/` | CC-BY-4.0 | [`LICENSES/CC-BY-4.0.txt`](../LICENSES/CC-BY-4.0.txt) |
| Third-party code (`third_party/`) | its own licence in each folder | [`LICENSE`](../LICENSE) |
| Qt's Arabic base catalogue (`translations/qtbase_ar.qm`) | Qt licensing / LGPL-3.0-only | `baseline/windows-arabic-v8/source/QT-TRANSLATIONS-COPYRIGHT.txt`, `LGPL-3.0-only.txt` |
| Sa6i Link logo, icon, local guide, reviewed Arabic catalogues | part of this private test | `sa6i/assets/`, `baseline/windows-arabic-v8/source/` |

The v8 package also ships copies of the licence texts in
`baseline/windows-arabic-v8/source/` and its own `LICENSE` file.

## Trademarks

NectarLink's [`TRADEMARKS.md`](../TRADEMARKS.md) says modified versions must
use their own name and logo. Sa6i Link does so (supplied logo and
`Sa6i-Link.ico`); internal package paths, update URLs and credits were left
intact by the original patch chain. Do not distribute a modified build under
the NectarLink name or logo, or imply endorsement.

## Review tools

The Arabic review used open-source tools only: LanguageTool 6.6
(`https://github.com/languagetool-org/languagetool`), Hunspell
(`https://github.com/hunspell/hunspell`) with Debian's AyaSpell Arabic
dictionary (`https://github.com/linuxscout/ayaspell`). Their results are leads,
not verified translations; expert human review is still required.

## Private test notice

The Windows v8 package and Android APK are experimental. The assembled Windows
folder and Android APK still need testing on Windows 7 and the OPPO A54. Do not
use the original updater with the Windows test build.
