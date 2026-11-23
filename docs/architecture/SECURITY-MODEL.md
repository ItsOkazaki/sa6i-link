# Security and permission model

The product reads a machine and then changes it. That ordering is the whole
security design: reading is bounded and auditable, writing is registered and
consented. This document is the contract for both.

## 1. Trust boundaries

| Boundary | Crosses it | Control |
| --- | --- | --- |
| Collector → engine | numbers and enums, no raw OS handles | typed structs only; no `String` from the OS reaches a rule unparsed |
| Engine → actions | `ActionId` + typed args | registry lookup, default deny |
| Engine → model | structured `ExplainContext` | redaction, schema, size cap |
| Model → UI | prose + registered ids | validation, template fallback |
| App → phone | existing iroh/QUIC + CBOR (unchanged) | existing pairing and protocol versioning |
| App → network | Ollama on loopback; cloud only if opted in | allowlist, no telemetry endpoints |

## 2. Permission tiers (what each needs)

| Capability | Rights needed | Available now |
| --- | --- | --- |
| CPU, memory, volumes, process summary | none | yes |
| Disk throughput (PDH), GPU memory (`QueryVideoMemoryInfo`) | none | yes, Win10+ for GPU |
| Defender / firewall / BitLocker state | none for some readings, **admin for full state** | partial — report `Unknown` where admin is required |
| Startup inventory (Run keys, Startup folder) | none | yes |
| Temperatures, fan speeds | kernel driver + admin | **refused** — no helper ships |
| Cleanup inside user profile (temp, caches, recycle bin) | none | planned, risk 1 |
| Disk cleanup outside profile, WinSxS, drivers | admin | **out of scope** |
| Registry repair, service changes, driver install, defrag | admin | **forbidden** |

Nothing in the default experience prompts for UAC. If a feature cannot work
without elevation, it says so and offers no button.

## 3. Data handling

- **Stays local, always**: samples, findings, action history, audit log, device
  identity, pairing keys.
- **Process names** are stored; full command lines are **not** (they carry
  secrets). Paths are stored as-is locally but redacted before any model call.
- **No telemetry.** The product does not phone home. Update checks are explicit
  and visible when they exist.
- **Deletion**: retention is visible in Settings (24 h raw, 30 days hourly,
  30 days findings, audit permanent) with a "delete everything" button that
  actually deletes the database file.
- **Export**: a report is a file the user chooses; it includes evidence and
  timestamps, and warns if it contains a machine name.

## 4. AI-specific controls

1. Input is a struct, never a conversation transcript and never raw file content.
2. Redaction runs before serialisation: usernames, machine name, network
   addresses, paths outside allowlisted roots, and any value matching a
   key/token pattern.
3. The exact payload is viewable with a "show what will be sent" control before
   the first cloud call, and on demand afterwards.
4. Output must parse against the versioned schema; unknown action ids are dropped,
   unknown fields are ignored, and prose is capped.
5. No tool calling. Ever. Naming an action is a suggestion to the user, not an
   execution path.
6. Loopback only by default (`127.0.0.1:11434`). Cloud providers are opt-in per
   provider with a clear notice, and the UI shows a badge for which one wrote the
   current text.
7. Model output is never shown as a measured value. Numbers on screen always come
   from the sample store.

## 5. Action safety

Required of every registered action: type-level arguments, precondition re-check
immediately before execution, a single in-flight action per machine, a timeout,
protected-path list (`System32`, `Windows`, `Program Files*`, user documents,
drivers, `.git`, anything with a system attribute), a byte/entry budget, dry-run
where meaningful, post-verification, and rollback or an explicit
"this cannot be undone" line.

Forbidden without exception: `format`, `diskpart clean`, `bcdedit`, deleting
outside the computed allowlist, disabling Defender/firewall, editing
`HKLM\SYSTEM`, driver installation, `cmd /c` or any string command.

## 6. Supply chain

`deny.toml` already allows a licence set and forbids GPL in the MPL core crates;
CI runs it. New dependencies must justify themselves against "does the standard
library plus `windows` cover this?" — for the first slice the answer has been yes.
Fonts are OFL with their licence files. No runtime downloads of models, rules or
binaries.

## 7. Known exposures outside the code (must be fixed, not documented away)

1. **Android signing keystore and its plaintext password are on a public-by-link
   Drive folder.** Anyone with the link can sign an update that devices accept.
   Rotate the key or move it to a secret store; do not ship links to it.
2. Candidate builds are distributed by public link, not signed releases, so users
   cannot verify what they run.
3. The hosted cleaner runs unsandboxed with the user's rights and can delete data;
   it is labelled, but the label is a mitigation, not a control.

These are process fixes and belong to the roadmap (M0), not to a future release.

## 8. Abuse and failure modes considered

| Case | Behaviour |
| --- | --- |
| Rule fires on a transient spike | hysteresis (`for = "10m"`) and confidence levels |
| Model suggests deleting a system folder | id not in registry → dropped before display |
| User clicks an action twice | second click sees the lock; UI shows the running action |
| Action partially succeeds | verification catches it, rollback runs, audit records both |
| Clock jumps / DST | windows stored as monotonic offsets plus wall clock; gaps rendered as gaps |
| Corrupt sample database | falls back to in-memory and says so |
| Another process deletes a file mid-clean | precondition re-check aborts, nothing else runs |
