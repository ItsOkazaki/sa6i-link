# Sa6i Link

Sa6i Link is an experimental rebrand of [NectarLink](https://github.com/thtbee/nectarlink) for connecting an Android phone to a computer. This private test is based on NectarLink 0.1.5 and is not an official NectarLink release.

## Download

Download the [Windows Arabic v8 test package](https://github.com/ItsOkazaki/sa6i-link/releases/tag/sa6i-windows-arabic-v8-test). The release includes the app folder and a checksum file. It is not an installer.

For Windows 7 x64, extract the package to a new folder, enable VxKex for `Sa6i-Link-Win7-UI-v8.exe`, and run `Start Sa6i Link v8.exe`. VxKex is not included. Read `START-HERE.txt` in the package before testing, and keep your previous working version as a backup.

To select Arabic in the Windows app, open **Settings → General → Language → More → العربية**.

## Test status

The assembled Windows package has not been tested on Windows 7 or with a phone. Arabic needs further human review, full right-to-left layout is unfinished, and the requested performance presets are not included. On Android 11, the test app is intended to follow the phone's system language; in-app language selection remains unresolved. See [test status](sa6i/STATUS.md) for details.

## Source and licences

The source is based on [NectarLink v0.1.5](https://github.com/thtbee/nectarlink/tree/v0.1.5). The Windows test is a binary/resource patch, not a source-built Sa6i Link release. Build instructions for the upstream source are in [UPSTREAM-README-v0.1.5.md](UPSTREAM-README-v0.1.5.md).

See [licensing and attribution](sa6i/NOTICE.md), [LICENSE](LICENSE), and [LICENSES](LICENSES/).
