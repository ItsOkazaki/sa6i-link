# Stage D — Screen inventory

Every screen states what it shows, which states it must handle, and how far it is
from existing work. Status tags: **verified** (works today, code read),
**partial**, **not implemented**, **needs external integration**, **technically
uncertain**.

## Existing screens (unchanged by this plan, restyled only)

| Screen | Today | Note |
| --- | --- | --- |
| `WelcomePage` / `WalkthroughPage` / `PairingPanel` | **verified** | Pairing is real (QR + code, iroh transport) |
| `HomePage` | **verified**, restyled | becomes **Pulse** |
| `MessagesPage`, `CallsPage` | **verified** | SMS/MMS, call log; notifications live in the Island |
| `PhotosPage`, `AppsPage`, `TimelinePage`, `DeckPage` | **verified** | phone storage, app list, timeline, Deck remote |
| `SettingsPage` | **verified** | gains AI provider and permissions sections |
| `MirrorWindow`, `ShelfWindow`, `IslandWindow`, `LaserOverlay` | **verified** | mirroring, shelf, notification island, laser pointer |

## New screens

| # | Screen | Purpose | States it must handle | Status |
| --- | --- | --- | --- | --- |
| 1 | **Pulse** (Home) | one sentence about the machine, top three findings, link state, the loop | no data yet / sampling / stale / partial (some metrics Unknown) / no phone paired | **not implemented** |
| 2 | **Monitor — Overview** | CPU, memory, disks, network, GPU tiles with sparklines | collecting, Unknown metric, Win7 gaps, machine under load | **not implemented** |
| 3 | **Monitor — Detail** (per subject) | the 60/1440-sample history for one metric, with gaps drawn as gaps | no history yet, retention exceeded, clock changed, timezone shift | **not implemented** |
| 4 | **Doctor** | findings for this machine, ranked, each with evidence | clean machine (no findings — rare and must be believable), stale finding, dismissed finding, rule could not run | **not implemented** (the shipped `doctor.rs` is *connection* diagnostics only) |
| 5 | **Doctor — Finding** | severity, evidence, what it means, candidate actions | no safe action available, action needs admin (refused), evidence window moved | **not implemented** |
| 6 | **Evidence drawer** (overlay) | metric path, samples, threshold, sample ids | sparse samples, Unknown | **not implemented** |
| 7 | **Action sheet** | exactly what will happen, what will change, how it will be verified, rollback | precondition failed, timed out, verification failed, rolled back | **not implemented** |
| 8 | **Audit log** | every action ever attempted, with pre/post state | empty, filtered, export | **not implemented** |
| 9 | **Clean** | storage analysis and cleanup | scan running / cancelled / nothing found / permission denied on a folder | **partial** — hosted Electron cleaner only, labelled; native engine **not implemented** |
| 10 | **Link** | devices, transfer, mirror, sync, clipboard, notifications | no devices, device offline, transfer in progress / paused / failed, wrong SOS code | **verified** (existing pages) |
| 11 | **Security** | OS update state, Secure Boot, Defender state, firewall, startup inventory, weak settings | Defender off/unavailable, third-party AV, domain-managed PC, Win7 (no Secure Boot) | **not implemented**; some readings **technically uncertain** without admin |
| 12 | **Assistant** | ask about *this machine's measured state*, propose registered actions | no local model, model too slow, cloud disabled, redaction removed something, model returned an unregistered action | **not implemented** |
| 13 | **AI settings** | choose provider, test, see exactly what would be sent | Ollama not running, model missing, cloud key absent, offline | **not implemented** |
| 14 | **About / Licences** | version, build, third-party notices | — | **verified** (existing notices pipeline) |
| 15 | **Capability matrix** (settings pane) | what this PC can and cannot measure or do, per module | — | **partial** (`capabilities.md` exists for Link) |

## Cross-cutting states every new screen must implement

| State | Requirement |
| --- | --- |
| **First run** | explain what will be read (no admin, no upload), then start sampling; no empty charts |
| **Sampling** | spinner with the real elapsed time, not a fake progress bar |
| **Unknown metric** | hatched block + reason + "not available on this system"; never `0` |
| **Stale** | dimmed values, timestamp visible, one-click re-sample |
| **No permission** | say which permission, why it is needed, what still works without it |
| **Error** | typed error with a next step; never a raw stack trace |
| **Offline / no model** | Assistant says "rules only" and still answers from the model of the machine |
| **Reduced motion / Win7** | static equivalents (see SIGNAL-THEME §7) |

## Deliberately absent

No "AI chat" as the front door (the front door is the machine's state), no
gamified health score out of 100 (unfalsifiable), no "boost" button, no live
"optimising…" theatre, no cloud dashboard, no account wall.
