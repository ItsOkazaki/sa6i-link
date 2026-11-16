# Browser version — noted, not decided, not built

**Status: deferred.** You asked whether a browser version is possible; a hybrid
was suggested, but you have not decided to build it. This file only records the
idea so it is not lost. No browser code, prototype or dependency was added.

## The suggested hybrid

Keep the **native** pieces where the OS requires them, and put only the
**interface** in a browser:

- Native phone service (Android app: notification access, screen capture,
  accessibility/control, pairing, file access).
- Native PC service (Windows 7 x64: the Rust core, Wi-Fi discovery, mirroring,
  PC control, the existing compatibility shim).
- Browser UI served locally by the PC service, talking to it over a local
  WebSocket / HTTP bridge (local-first, no account, no cloud) — the same UI
  layout as NectarLink, plus Arabic/RTL handled with CSS `dir="rtl"`.

## Constraints to settle before any decision

- A browser cannot do Android notification access, screen capture, ADB or
  accessibility input by itself — those stay native, so the hybrid does not
  remove either native app.
- Windows 7 browser support is limited; a local browser UI still needs a
  modern engine, and the target browsers on that PC must be checked.
- Screen mirroring latency/encoding, local TLS or loopback-only transport, and
  how the phone service reaches the PC service on the same Wi-Fi all need a
  design.
- Pairing/identity, encryption and the existing end-to-end model must survive
  the extra browser hop.
- It is a separate workstream from the current Windows 7 / Android 11 Arabic
  test; it does not fix RTL, presets, window buttons or the Android 11 picker.

## Decision needed

Nothing to do until you say so. If you decide to build it, the likely first
step is a small read-only prototype (status + guide) against a local PC
service, reusing `sa6i/assets/sa6i-link-logo.png`, before touching mirroring
or control.
