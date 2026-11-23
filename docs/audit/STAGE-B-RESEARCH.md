# Stage B — Research report

Scope: what to reuse, wrap, adapt or implement for Sa6i Monitor, Doctor,
Security and the intelligence layer, on Windows, inside this repository's
constraints.

Licences here were checked against the projects' own repositories rather than
recalled. The repository's dependency policy (`deny.toml`) already allows
Apache-2.0, BSD, ISC, MIT, MPL-2.0 and similar, and **forbids GPL inside the
MPL-2.0 core crates**; the apps themselves are GPL-3.0-or-later.

---

## 1. Candidate projects

| Project | What it provides | Stack | Licence (verified) | Maintenance | Integration cost | Determination |
| --- | --- | --- | --- | --- | --- | --- |
| **LibreHardwareMonitor** | Temperature, fan, voltage, clocks, load; the only realistic source of motherboard sensors | C# / .NET; kernel driver (WinRing0 family) for low-level access | **MPL-2.0** ([repo](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)) | Active (0.9.6, Feb 2026) | High: a .NET runtime beside a Rust/Qt app, plus an **admin-loaded kernel driver** | **Do not embed.** Use native APIs for everything else; offer temperatures only through an opt-in elevated helper later, clearly marked |
| **scrcpy** | Screen mirroring/control via `scrcpy-server` | Java server + native client | **Apache-2.0** | Very active | None needed | **Not adopted**: this app already implements mirroring natively (`core/…/mirror.rs`, MF decode + D3D11). Keep as protocol reference only |
| **BleachBit** | Cleaner with XML (CleanerML) rule definitions | Python + GTK | **GPL-3.0-or-later** ([repo](https://github.com/bleachbit/bleachbit)) | Active (6.0.x) | High: Python runtime; also drags a GUI stack | **Adapt the idea, not the code.** Write our own rule format and our own definitions; cite BleachBit as the taxonomy reference. Vendoring would be licence-compatible but engineering-hostile |
| **KDE Connect** | The reference phone↔PC feature set | C++/Qt | GPL-2.0-or-later | Active | — | **Reference only.** The transport (iroh/QUIC) and protocol differ fundamentally from this project's |
| **LocalSend** | Cross-platform local file transfer protocol | Dart/Flutter | **Apache-2.0** ([site](https://localsend.dev/)) | Very active | Already done | **Already reimplemented** in Rust (`core/…/localsend.rs`). No new work |
| **Ollama** | Local LLM runtime with an HTTP API | Go, MIT-style permissive | **MIT** | Very active | Low: `POST /api/chat` on `127.0.0.1:11434` | **Integrate via API, never vendor.** Provider abstraction with a deterministic fallback |

### Why not LibreHardwareMonitor as a dependency

It is the only serious source of temperatures and fan speeds, and MPL-2.0 would
be compatible. The blockers are engineering, not legal:

1. It needs a **.NET runtime** inside a Qt/Rust product — a second runtime,
   second updater, second security surface.
2. Sensor access uses a **kernel driver that must be loaded with administrator
   rights**, and that driver class has a long history of privilege-escalation
   advisories. Shipping it would contradict "least privilege" and would need
   its own review and signing.
3. It would be the only component that can hang or bugcheck the machine.

Determination: **no driver in the first slice.** Temperatures are declared
*Unavailable — requires an elevated sensor helper*, rather than shown as fake
numbers. This is exactly the honesty rule in the brief.

---

## 2. Windows telemetry sources (verified API classes)

Legend: **A** = needs administrator, **W7** = available on Windows 7.

| Metric | API | Cost | Notes |
| --- | --- | --- | --- |
| CPU total | `GetSystemTimes` | trivial | W7 |
| CPU per core | `NtQuerySystemInformation(SystemProcessorPerformanceInformation)` | trivial | W7; undocumented but stable, used by every monitor |
| RAM / commit | `GlobalMemoryStatusEx`, `GetPerformanceInfo` | trivial | W7 |
| Per-process CPU/RAM | `NtQuerySystemInformation(SystemProcessInformation)` single snapshot | low | Avoid `EnumProcesses` + per-handle loops (N× slower) |
| Volumes, free space | `GetLogicalDrives`, `GetDiskFreeSpaceExW`, `GetVolumeInformationW` | trivial | W7; **not** `GetDiskFreeSpace` (32-bit truncation) |
| Disk activity | PDH `\PhysicalDisk(*)\% Disk Time`, `\LogicalDisk(*)\Disk Bytes/sec` | low | W7; must use `PdhAddEnglishCounter` (localised counter names break otherwise) |
| Disk health | `MSFT_PhysicalDisk` (WMI `root\Microsoft\Windows\Storage`) | medium | **Win8+**; report *Unknown* on W7 |
| SMART predict failure | `IOCTL_STORAGE_PREDICT_FAILURE` | low | **A**; may still be unsupported by the device |
| NVMe/SATA detail | `IOCTL_STORAGE_QUERY_PROPERTY` | low | Partial data without admin |
| GPU memory | `IDXGIAdapter3::QueryVideoMemoryInfo` | low | W10+; no admin |
| GPU utilisation | PDH `\GPU Engine(*)\Utilization Percentage` | medium | **W10 1709+**, not W7 |
| Temperatures / fans | *no public user-mode API* | — | Only via kernel driver (see §1) → **Unavailable** |
| Startup items | `HKCU/HKLM …\Run`, `StartupApproved`, Startup folder, `ITaskService` (Task Scheduler COM), `OpenSCManager`/`EnumServicesStatusEx` | medium | Registry + COM; W7 |
| Event log | `wevtapi` (`EvtQuery`, `EvtNext`, XPath filters) | medium | W7; System/Application readable **without** admin |
| Processes + parents | `NtQuerySystemInformation` gives `InheritedFromUniqueProcessId` | low | Needed for "who started this" evidence |
| Network connections | `GetExtendedTcpTable` / `GetExtendedUdpTable` | low | W7; maps pid↔port |
| Firewall state | `INetFwPolicy2` (`NetFwPolicy2`/`NetFwRule`) | low | W7 |
| Binary trust | `WinVerifyTrust` + `GetFileVersionInfoW` | low | Per-file; cache by path+size+mtime |
| Defender status | WMI `root\SecurityCenter2` (`AntiVirusProduct`) | low | W7+; limited to enrolled AV products |
| UAC / Secure Boot / BitLocker | Registry `HKLM\…\SecureBoot\State`; `Win32_EncryptableVolume` (A) | low | Report per-item availability |

**Everything in the Monitor slice is obtainable without administrator rights.**
That is the single most important finding of this stage: a credible Monitor does
not need elevation, so it can ship without any privilege prompt.

---

## 3. Rust dependencies

Already in the workspace and sufficient: `windows` 0.62, `serde`/`serde_json`,
`rusqlite` (bundled SQLite), `tokio`, `tracing`, `anyhow`. Nothing new is
required for the first slice.

| Candidate | Licence | Verdict |
| --- | --- | --- |
| `sysinfo` | MIT | **Not for the Windows path.** Its Windows backend is shallower than the APIs above (no PDH, no process parents, no per-core kernel/idle split) and would hide the availability distinctions we must display. Useful later for macOS/Linux parity. |
| `wmi` | MIT | Optional; COM latency and WMI service dependency. Prefer direct `windows` bindings; use WMI only where there is no Win32 API (`MSFT_PhysicalDisk`, `SecurityCenter2`). |
| `evtx` | MIT/Apache | Not needed — `wevtapi` through the `windows` crate avoids parsing offline files. |
| `winreg` | MIT | Not needed; `windows` has registry bindings. |

---

## 4. Compatibility determinations

1. **Windows 10/11 first** (decision D3). Windows 7 keeps the Link features it
   already has; Monitor degrades per-metric with an explicit "not supported on
   this Windows version" state, never a zero.
2. **No kernel drivers, no elevation** in Monitor, Doctor or Security.
3. **AI is optional.** Rules produce findings with template text; the model only
   rephrases and prioritises. With Ollama absent, the product is still complete.
4. **No third-party engine is vendored** in the first slice; the only external
   runtime dependency remains the user's own Ollama, if they choose to install it.

## 5. Open questions for Stage C/D

- Retention and sampling cadence for history (see architecture).
- Whether Security's persistence inspection should reuse Doctor's startup
  collector (recommended: one collector, two presentations).
- Whether the existing embedded cleaner stays in the navigation during the
  native Clean build-out, and under which label.
