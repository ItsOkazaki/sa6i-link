# Can `docker-android` test the Sa6i Link APK?

**Short answer: yes, partially.** [`HQarroum/docker-android`](https://github.com/HQarroum/docker-android/)
(MIT, v1.1.0) runs a headless Android emulator in Docker with ADB on port 5555
and scrcpy for the screen. It can install and smoke-test the APK, and it is the
best available way to check the **Android 11 system-language** behaviour
without the OPPO A54. It **cannot replace real-device testing**, and there is
one blocker to resolve first: the APK's native libraries.

This is an assessment only. Docker is not installed in this sandbox, so nothing
here has been executed.

## What I inspected (2026-11-16)

The Android test APK in Google Drive (file ID
`1pD5q0r5UiKjOIT0xBBhWNqALevDlI7Rb`, 53,278,990 bytes, SHA-256
`86913c1ab9ac5f1aac060b966708a0fc4442fd56e02df7cbc2dc4a4a1d92b5b1`) was
downloaded and inspected directly:

| Finding | Value |
|---|---|
| Package / version | `app.sa6ilink.test`, `0.1.5` (105999), label **Sa6i Link** |
| SDK | `minSdk 26`, `targetSdk 37`; 8 activities, 11 services |
| Signature | `META-INF/SA6ITEST.{RSA,SF}` — sideloadable with `adb install` |
| Arabic | present in `resources.arsc` (`إقران`, `الحاسوب`, `Sa6i Link`); no `values-ar` folders because resources are compiled |
| Native libs | `libnectarlink_ffi.so` + two `libiroh*.so` exist **only** in `arm64-v8a` and `armeabi-v7a` |
| x86 / x86_64 libs | only 6 generic libs each (graphics, spake2, conscrypt, jnidispatch, image processing, surface util) — **no core FFI lib** |

`docker-android` defaults to `API_LEVEL=33`, `IMG_TYPE=google_apis`,
`ARCHITECTURE=x86_64`, Pixel device preset. Only `x86_64` and `x86` are
actively supported. It needs `/dev/kvm` and `--privileged`, exposes
`127.0.0.1:5555` for ADB, and Docker Hub tags look like `api-33`.

## The blocker: ABI mismatch

On the default x86_64 image, Android will pick the x86_64 libs and the app will
probably fail when it loads `libnectarlink_ffi.so` (`UnsatisfiedLinkError`), or
`adb install` will return `INSTALL_FAILED_NO_MATCHING_ABIS`. Android 11 (API 30)
**Google APIs x86_64** system images are reported to include ARM64→x86_64 NDK
translation (`libndk_translation`), which can run the arm64 build — but support
varies by image type/build and must be verified; Play Store images and some
builds do not ship it. Sources: [OWASP MASTG testing setup](https://github.com/OWASP/mastg/blob/master/Document/0x05b-Android-Security-Testing.md),
[AOSP 11 native-bridge notes](https://chgans.design.blog/2021/05/23/adding-arm-native-bridge-to-the-aosp11-x86-emulator/).

Three ways forward, in order of effort:

1. Build `API_LEVEL=30`, `IMG_TYPE=google_apis`, `x86_64` and test whether the
   arm64 libs load via translation. Fastest, **unverified**.
2. Use an `arm64-v8a` system image (full QEMU emulation, slow) — note
   `docker-android` only officially supports x86/x86_64, so this needs a
   different image such as the projects in its "See also" section.
3. Rebuild the APK with x86_64 `libnectarlink_ffi.so` + iroh libs. Needs the
   Rust core + Android NDK build, which is not available in this sandbox.

Also: `install_android.sh` contains a hard-coded `ANDROID_VERSION="api-33"`
string, so check that script when building an API 30 image; the Dockerfile's
`API_LEVEL` build arg is the intended lever. And `targetSdk 37` is newer than
the API 30 emulator — sideload still works, but target-Sdk-gated behaviour
follows API 30, not 37.

## What it CAN test (once the app launches)

- `adb install -r`, launch, crash / logcat / ANR checks, permissions granted
  via `adb` (notification access, accessibility), MediaProjection prompt
- **Android 11 language behaviour**: API 30 has no per-app language picker, so
  setting the emulator's *system* locale to Arabic exercises exactly the
  "follow the phone's system language" path that the test intends. scrcpy
  screenshots then show Arabic strings, plurals and right-alignment
- UI navigation, repeatable CI smoke checks
- The repo's JVM unit tests (`android/app/src/test/…`, including
  `LocalesTest`) need **no emulator at all** — run them with Gradle directly

## What it CANNOT test

- OPPO A54 / ColorOS 11 vendor permission dialogs, battery optimisation, real
  Wi-Fi pairing with the Windows 7 PC. The emulator sits behind Docker NAT, so
  mDNS/NSD discovery of the PC will likely need `--network host`, an
  `adb reverse`/manual IP workaround, or a different network setup.
- Real phone mirroring / PC-control latency and fidelity, real camera,
  telephony, SMS, Bluetooth, hardware performance, VxKex or the Windows 7
  window-button fixes.
- Expert human Arabic review, complete RTL layout on real hardware, or the
  (still unimplemented) performance presets.

## Where it runs

Requires a Linux host with `/dev/kvm` and a privileged container. The
**Windows 7 x64 target PC cannot host it** (Docker Desktop needs Windows
10+/WSL2/Hyper-V), and Docker is absent here — so run this on a separate Linux
machine or CI runner, not on the test PC.

## Recipe (for a Linux host with Docker + KVM; unverified)

```bash
# Build an Android 11 / API 30 image, or check Docker Hub for an api-30 tag
docker build --build-arg API_LEVEL=30 --build-arg IMG_TYPE=google_apis \
             --build-arg ARCHITECTURE=x86_64 -t sa6i-emulator .
docker run -it --rm --device /dev/kvm -p 5555:5555 -p 5554:5554 \
           --privileged sa6i-emulator

# In another shell
adb connect 127.0.0.1:5555
adb install -r Sa6i-Link-Android-Arabic-Reviewed-TEST.apk   # watch for NO_MATCHING_ABIS
adb shell setprop persist.sys.locale ar-EG
adb reboot
adb shell am start -n app.sa6ilink.test/.MainActivity 2>/dev/null || true
adb logcat | grep -i sa6i
scrcpy                                                     # screenshots / UI checks
```

`INSTALL_FAILED_NO_MATCHING_ABIS` or a missing `libnectarlink_ffi.so` at
runtime is the ABI blocker above, not a corrupt APK. Keep the OPPO A54
real-device checklist in [`STATUS.md`](STATUS.md) regardless of the result.

## Decision

Not adopted as the primary test target yet. It is a useful **complement** for
CI smoke tests and the Arabic/system-language question, but the ARM/x86 native
library issue must be resolved first, and real-device testing stays required.
