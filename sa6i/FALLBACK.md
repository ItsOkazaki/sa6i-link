# Downloads and fallback

The v8 Windows package is experimental. Keep your previous working v4/v5 installation separately and back up preferences and pairings; different versions may share them.

## Windows v8 full folder

Download `Sa6i-Link.zip` from the [GitHub prerelease](https://github.com/ItsOkazaki/sa6i-link/releases/tag/sa6i-windows-arabic-v8-test). It contains the v8 app files and runtime files from the supplied app folder, but is not an installer and does not include VxKex. A startup error has been reported; see [startup troubleshooting](STARTUP-TROUBLESHOOTING.md). Phone testing is still needed.

1. Extract the ZIP to a new folder without overwriting your existing installation.
2. Read `START-HERE.txt` in the extracted folder. Enable VxKex for `Sa6i-Link-Win7-UI-v8.exe` as with the previous build.
3. Run `Start Sa6i Link v8.exe`. For Arabic, select **Settings → General → Language → More → العربية**.
4. Do not use the original updater or copy DLLs into Windows system directories. If needed, quit v8 and use the previous launcher.

ZIP SHA-256: `f468df636501253d2cc35072871d70040714bb4d30ff915463dd9cc2ce01f3ce`. The release checksum file uses the original filename `Sa6i-Link-Windows-v8-Full-Folder-TEST.zip`; rename a downloaded copy to that name before running `sha256sum -c SHA256SUMS-FULL-FOLDER.txt`.

## Original patch archive

`fallback/Sa6i-Link-Windows-Arabic-v8-Reviewed-TEST.zip` is the original **patch only**, not a complete app folder. It requires an existing working app folder with its Qt DLLs and `cldapi.dll`. Its [checksums](fallback/SHA256SUMS.txt) cover the ZIP and extracted files. The extracted patch and its original instructions are in `baseline/windows-arabic-v8/`.

## Previous build and Android

Keep the previous v4/v5 files on your PC or in your own backup; the original patch archive is not a replacement for them. The Android Arabic test APK remains external to this repository and needs device testing.
