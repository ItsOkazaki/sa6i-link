# Stage A — Repository audit

Status: **findings for review. No architectural changes made.**
Scope: the checkout at `arena/077ce3b0-sa6i-link` (tip `7402bf1`), plus the
delivery work under `sa6i/clean/`.
Method: static inspection of tracked files — manifests, module layout, ADRs,
protocol docs, tests and CI. Nothing here was executed on Windows or Android,
so every runtime claim is attributed rather than asserted.

---

## 1. What this repository actually is

Sa6i Link is a **rebrand of NectarLink 0.1.5**, a mature phone↔PC bridge. The
rebrand is a private test build, not an official release (`sa6i/NOTICE.md`).

| Area | Reality | Size |
| --- | --- | --- |
| Desktop app | **Qt Quick (QML) UI + Rust**, bridged with cxx-qt; `windows-rs` for OS integration | 52 `.rs` files, 84 QML files (29,341 lines) |
| Shared engine | Rust workspace: `sa6i-link-core`, `-protocol`, `-adb`, `-cli`, `-ffi` | 37 core modules, 32,397 lines |
| Android app | **Kotlin + Jetpack Compose**, core via UniFFI | 145 Kotlin files, 47,959 lines |
| Website | Vite + React 19 marketing site (not the product UI) | `website/` |
| Totals | 878 tracked files | ≈93,600 lines Rust, ≈48,000 Kotlin, ≈29,300 QML |
| Tests | 932 `#[test]` / `#[cfg(test)]` markers in `core` + `desktop`; QML component tests; Python test suites in `sa6i/clean` | — |
| CI | 13 workflows, 8 of them `sa6i-clean-*` | `.github/workflows/` |
| Decisions | ADRs 0001–0008 (shared Rust core, iroh transport, CBOR wire format, Qt Quick UI, Kotlin/Compose Android, licensing, distribution) | `docs/adr/` |

**The requested stack (Tauri 2 + React + TypeScript + Rust) does not describe
this project.** The desktop UI is Qt Quick and the Android app is native
Kotlin. Adopting Tauri/React would mean replacing ~29,000 lines of working QML
and re-certifying every Windows integration — mirroring surfaces, virtual
camera, overlays, tray — none of which Tauri provides. This is decision D1
below and it blocks everything else.

Transport and protocol are iroh (QUIC, device keys, hole punching, relay) with
a CBOR wire format and a versioned spec in `docs/protocol/`. Capability
negotiation is real: `features.rs` computes an Available/Partial/Locked/
Unsupported matrix that both apps render, so phone and PC cannot disagree.

---

## 2. Feature status matrix

Evidence types:

- **code** — the implementation is present and wired in this checkout, read at
  the cited path.
- **claimed** — the project's own `docs/PLAN.md` §3 marks it `(done)`; not
  reproducible from here.
- **external** — needs hardware, a signed package, or a third-party service.
- **absent** — no implementation found.

| Module | Feature | Status | Evidence |
| --- | --- | --- | --- |
| Link | Pairing (QR, nearby + code, USB auto-pair) | code + claimed; USB pair verified only on emulator | `core/…/pairing.rs` (640 lines), `desktop/app/src/qr.rs`, `setup/` |
| Link | Reconnect after sleep, Wi-Fi change, reboot | claimed | `core/…/session.rs`, `node.rs` |
| Link | Transport: LAN, USB, away-from-home relay | code | ADR-0003, `core/…/node.rs` |
| Link | Connection Doctor (firewall, public profile, AP isolation, VPN, OEM killers) | code | `desktop/app/src/doctor.rs` (718 lines) + `win/doctor` |
| Link | Notifications mirroring, actions, inline reply, DND, OTP | claimed; code present | `core/…/notifications.rs`, `notp.rs`, `desktop/app/src/notifications.rs` |
| Link | SMS/MMS, unified conversations, contacts | claimed; code present | `core/…/sms.rs`, `contacts.rs`, `desktop/app/src/messages.rs` |
| Link | Calls: alert, in-call controls, log, dialer | claimed; code present | `core/…/calls.rs`, `desktop/app/src/calls.rs` |
| Link | Clipboard text/images/rich, history, smart chips | claimed; code present | `core/…/clipboard.rs`, `clipboard_history.rs`, `clip_kind.rs` |
| Link | File transfer, resumable, multi-stream, BLAKE3 | code | `core/…/transfer.rs` (2,338 lines) |
| Link | LocalSend protocol interop | code | `core/…/localsend.rs` |
| Link | Folder sync, photo backup, phone storage in Explorer | claimed; code present | `desktop/app/src/folder_sync.rs`, `photo_backup.rs`, `pc_storage.rs`, Cloud Files shim |
| Link | Screen mirroring (H.264/H.265/AV1, hardware decode, input) | claimed; code present | `core/…/mirror.rs` (1,007 lines), `desktop/app/src/mirror.rs`, `pc_mirror.rs` |
| Link | Phone as webcam (Windows 11 virtual camera) | claimed; 4K unverified on hardware | `desktop/vcam/src/shm.rs`, `desktop/app/src/webcam.rs` |
| Link | Deck, remote input, air mouse, voice typing | claimed; code present | `core/…/deck.rs`, `remote.rs`, `desktop/app/src/deck.rs`, `input_share.rs` |
| Link | Ambient surfaces: Island, Shelf, Command Palette, Timeline, Handoff | claimed; code present | `IslandWindow.qml`, `ShelfWindow.qml`, `timeline.rs`, `handoff.rs` |
| **Clean** | Embedded cleaner (third-party Electron app) | **partially integrated, by construction** | see §3 |
| **Clean** | Native treemap, duplicate hashing, storage history | absent natively; the Electron app provides its own | `sa6i/clean/CleanView.qml` hosts it |
| **Doctor** | System diagnosis, event log analysis, disk health, startup analysis | **absent** | `doctor.rs` is the *Connection* Doctor only |
| **Monitor** | CPU/RAM/disk/GPU telemetry, process list, history | **absent** | only `GetDiskFreeSpace`-class calls in `win/mod.rs` and `transfer.rs` |
| **Security** | Config checks, persistence inspection, network inspection | **absent** | — |
| **Assistant** | Natural language, shared context, explainable diagnosis | **absent** | zero `ollama`/`llm` references in the tree |
| **Intelligence** | Rule engine, evidence model, action registry, audit log | **absent** | — |

Everything under "Link" is the genuine asset here: a working, tested bridge
with a capability matrix, not a mock-up. Everything under Doctor/Monitor/
Security/Assistant — the entire premise of the new vision — does not exist yet.

---

## 3. Sa6i Clean: how integrated it really is

This matters because it is the one place where "integrated" could be
overstated, and the user asked explicitly that it not be.

- The cleaner is a **third-party packaged Electron application**. Its renderer
  talks to `window.cleanly`, exposed by `dist-electron/preload.cjs`; it needs
  its Electron main process for scanning, cleaning and OS operations. The React
  bundle alone is not a cleaner (`INTEGRATION.md`).
- It reaches Sa6i Link as an **embedded window with a native host adapter**
  (`native_embed.c/.h`, `qt_embed_adapter.cpp`, `host_lifecycle.c`,
  `viewport_geometry.c`, `CleanEntry.qml`, `CleanView.qml`, `CloseGate.qml`),
  with a launch guard that verifies the cleaner's digests before starting it —
  the contract that had to be retargeted when the bundle was debranded.
- It is **not** a native Sa6i module: no scan logic, no treemap, no duplicate
  detection, no cleanup engine lives in this repository. There is no sandbox:
  the cleaner can reach any path the user can, and it can delete data.
- The integration is guarded but not release-ready by the project's own
  assessment (`sa6i/clean/RELEASE-READINESS.md`, `SAFETY-REVIEW.md`,
  `QT-HOST-PLAN.md`), and the Qt build used for it is a **Windows 7 backport**
  whose licensing is unreviewed (`NOTICE.md`).

So: "Sa6i Clean" today is a *hosted foreign application wearing Sa6i branding*.
That is a defensible interim state and an indefensible final one if the product
promises a native storage engine.

## 4. Branding status (verified)

Changed and working: renamed executable (`Sa6i Link.exe`), its product-name
strings, window titles, the embedded cleaner's bundle (title, package name,
lowercase identifiers, bridge/channel names, emblem as inline data URI), the
removal of its Tip/Feedback navigation and the author's checkout/mail contact.

Still upstream, verified in tree:

| Item | Where |
| --- | --- |
| `AppxManifest.xml` identity, publisher, display strings | published package |
| Installer, updater and some platform labels | `desktop/installer`, `updater.rs` |
| QML resource inside the shipped executable (binary-patched, not source) | `INTEGRATION.md` |
| Translation filenames, `sa6i_link_vcam.dll` | package |
| Executable **icon** | icon transplant not yet completed on the Windows 7 test machine |

The brand is therefore *consistent where the user sees it* and *inconsistent
where a build system reads it*. That gap is item W1 in the roadmap.

---

## 5. Gap against the stated vision

| Vision pillar | Today | Distance |
| --- | --- | --- |
| Connect (Sa6i Link) | Real, deep, tested | Small — polish and Windows 10/11 targets |
| Understand (Doctor) | Only connectivity diagnosis | Large — telemetry, rules, evidence model |
| Optimize (Clean) | Hosted third-party app | Large — native engine or hardened host |
| Monitor | Nothing | Medium — Win32/WMI/PDH sources are well-trodden |
| Security | Nothing | Medium — read-only inspections are cheap and honest |
| Assistant | Nothing | Large — needs the evidence model first, not the other way round |

The requested intelligence pipeline (collect → normalize → rule → correlate →
evidence → explain → propose → approve → execute → verify → record) has **no
foundation** yet: there is no telemetry schema, no action registry, no audit
log. Building the chat surface first would produce a system that talks about
metrics it cannot obtain — exactly what the brief forbids.

---

## 6. Licensing (as recorded)

| Part | Licence |
| --- | --- |
| Desktop app, Android app, CLI | GPL-3.0-or-later + app-store exception |
| Core crates (`core/`, except CLI) | MPL-2.0 |
| Protocol spec, `docs/` | CC-BY-4.0 |
| Embedded cleaner | third-party, its own terms — **needs a written determination before shipping** |
| Qt (incl. W7 backport) | LGPL/GPL; backport licensing unreviewed |
| Upstream brand | `TRADEMARKS.md`: modified versions must use their own name and logo — satisfied |

GPL-3.0 on the desktop app is the binding constraint for the whole plan: any
new module compiled into that binary inherits it, and any third-party engine
(MIT/Apache) may be linked but not vendored under incompatible terms.

---

## 7. Risks and debt

| # | Risk | Why it matters |
| --- | --- | --- |
| R1 | The shipped executable is **not** the same artifact as this source (`INTEGRATION.md`: QML resource binary-patched; provenance unestablished) | Every future module needs a reproducible build of the real app, or features will exist in source and never reach the user |
| R2 | Windows 7 is the user's test machine; the project targets Windows 11 | Telemetry APIs differ; Win7 support must be a decision, not an accident |
| R3 | 8 of 13 workflows concern the cleaner | CI is dominated by an integration that is not the product's core |
| R4 | Profile/device-key binding to the product name | Already caused `0x8007000B`; any future rename must reset profiles |
| R5 | Cleaner has no sandbox and can delete data | A native engine changes the liability profile; must be designed, not inherited |
| R6 | 932 test *markers* ≠ 932 verified behaviours | Test depth per module is uneven; the audit doc should not be read as coverage |

---

## 8. What Stage B–E would produce

**Stage B — Research (1 deliverable).** Per-component determination for
LibreHardwareMonitor, scrcpy, BleachBit, KDE Connect, LocalSend, Ollama,
plus Windows telemetry stacks (WMI/CIM, PDH, ETW, `GetSystemTimes`,
`IOCTL_STORAGE_*`, SetupAPI, `WinVerifyTrust`). Each: what it provides, licence,
maintenance, integration complexity, and **reuse / wrap / adapt / implement**.

**Stage C — Architecture (1 deliverable + diagrams).** Telemetry schema,
evidence/finding model, rule engine boundaries, action registry with
permissions and audit log, AI provider abstraction (Ollama local + optional
cloud), module boundaries against the existing Rust core, and the IPC surface
between QML and the new engines.

**Stage D — Design (1 deliverable).** Token set from the stated palette,
type scale (Inter/Manrope + JetBrains Mono), screen inventory across the six
modules, and a geometric connected-S mark explored as standalone icon and
horizontal lockup — as vector, in-repo, no generated text.

**Stage E — Roadmap (1 deliverable).** Ordered by technical risk, with a
working demo path: Monitor (real numbers) → Doctor (rules over those numbers)
→ Clean (native scan, reuse of the existing host as fallback) → Security
(read-only checks) → Assistant (grounded on the evidence model).

---

## 9. Decisions needed before any of that is built

- **D1 — UI stack.** Keep Qt Quick/QML + Rust (recommended: it is the product,
  and Tauri brings no advantage for mirroring, overlays or the virtual camera),
  or migrate to Tauri 2 + React and accept a rewrite of the desktop UI.
- **D2 — Clean strategy.** Keep the hosted third-party cleaner as a
  clearly-labelled fallback while a native scan engine is built in Rust
  (recommended), or continue investing in the Electron integration as the
  product's storage story.
- **D3 — OS target.** Windows 10/11 as primary with Windows 7 as an explicitly
  degraded target, or keep Windows 7 first-class (constrains APIs and Qt).
- **D4 — Scope of "next level" for this phase.** Everything in the vision is
  multi-month. The first slice proposed here is: real telemetry + evidence
  model + Monitor page + Doctor rules over that evidence, with the Assistant
  reading the model and performing only whitelisted actions.
