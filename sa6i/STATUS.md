# Test status

Sa6i Link v8 is an experimental Windows 7 x64 binary/resource patch based on NectarLink 0.1.5. The assembled full-folder package has not been tested on Windows 7 or with a phone. A previous Windows 7 build was reported to work for Wi-Fi pairing, mirroring and PC control; retesting v8 is still needed.

## Available in the v8 test

- Arabic in **Settings → General → Language → More → العربية** and in the local guide. The translation has been checked with language tools but still needs expert human review.
- Sa6i Link branding, font and vector window buttons. These are binary patches and have not been fully ported to source; the window buttons need Windows 7 testing.
- A `cldapi.dll` compatibility shim. Phone storage in Windows Explorer is not supported by the shim.

## Known limitations

- Complete right-to-left layout is unfinished; global mirroring was disabled because of layout warnings.
- Smoother, balanced and sharper performance presets are not implemented.
- On Android 11 the test app is intended to follow the phone's system language. In-app language selection is unresolved; the APK needs real-device testing.
- The Android test APK is external to this repository. Emulator testing can help with basic checks, but ARM-only native libraries may prevent it running on an x86 emulator and it cannot replace testing on the OPPO A54.
- A browser interface is deferred and has not been built.

## Before testing

Keep the previous working v4/v5 installation and back up shared preferences and pairings. Extract the v8 full-folder package separately, enable VxKex for the v8 executable, and run its launcher. Do not use the original updater or copy DLLs into Windows system folders. See [FALLBACK.md](FALLBACK.md).

Test language switching and the guide, window buttons, Wi-Fi pairing, mirroring and PC control on the Windows 7 PC and OPPO A54. Check both Arabic and English system languages on the phone.
