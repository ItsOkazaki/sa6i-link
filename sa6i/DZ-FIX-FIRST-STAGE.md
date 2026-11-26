# DZ FIX: first-stage implementation design

Base: Hub dashboard commit bafc28083159a684b36648bb2ad1e80cfcc64baf. This is a design, not a completed implementation.

## Scope
A third Hub choice opens DZ FIX in the same main window; Back returns to Hub without restarting Link or Clean. The first stage is a user-initiated, read-only scan of network and basic Windows health. A scan neither requests elevation nor modifies files, settings, services, drivers, firewall rules or paired-device data. No automatic repair in this stage. Later repairs require per-action informed approval.

## Checks and interpretation
- Windows version: identify OS and report unsupported or unknown accurately.
- Network adapters: query Windows adapter status and usable address; distinguish API failure from absence of an address; explicitly state that an address does not prove internet connectivity. VPN and virtual adapters may make results ambiguous.
- Internet and DNS: if the user starts an internet test, disclose the named remote destination in the UI. A DNS lookup plus a bounded TCP connection to a named HTTPS host can indicate basic reachability, not prove that all websites or services work. Timeouts, offline status, captive portals, firewall restrictions and DNS failures must be described as possibilities rather than definite causes. Do not fetch or transmit local files or identifiers. Avoid unbounded DNS waits.
- System drive free space: read available bytes for the Windows system volume, with a cautious informational warning at a documented threshold. Disk space alone is not a diagnosis of slowness. A failed query is unknown, not healthy.
- Time and date: display current local time as informational, and ask the user to verify it; don't guess correctness without a trusted source.

## Safety and interaction
- Only fixed, reviewed diagnostic functions; never execute instructions produced by AI or arbitrary commands. No network access before explicit scan action and destination disclosure.
- Each result carries status (OK, attention, unknown, not tested), evidence, limitations and non-destructive next steps. Don't claim a root cause based on one signal.
- Later repair proposals must describe exact changes, risk, privileges, restart and rollback; each action has separate approval. Approval of a scan is not approval of a repair. UAC is an additional Windows permission prompt, not a substitute for informed approval.
- Never silently reset network settings, modify firewall, install drivers, delete data or reset pairings. Restore points/backups can fail or be unavailable and must not be represented as guaranteed.
- Avoid reusing the existing Connection Doctor fix dispatcher for this feature: it includes firewall mutation. Existing adapter helper currently returns a default value on API failure, so it cannot by itself distinguish error from no address.

## Implementation and test gates
1. Add a dedicated DZ FIX state/view to the Hub; leave Link core alive and coordinate Clean's native overlay. Test navigation, close/tray behavior, and connected-phone continuity.
2. Implement read-only Windows probes on background workers with explicit error and timeout results. No shell command construction from user input. Minimize collected data and do not persist or transmit diagnostic details by default.
3. Unit-test evaluation with synthetic healthy, failed, incomplete, VPN and low-space inputs; test worker timeout/errors and no-change behavior. Test Hub navigation and overlay behavior offscreen.
4. Build using the existing Win7 CI workflow. Verify build artifact and cleaner pins, assemble a separate test candidate with the established profile and launcher, verify hashes and archive. Close old app from tray before launching the candidate.
5. On real Windows 7 and OPPO: test Hub/Link/Clean navigation and connection preservation, run read-only checks in connected/disconnected scenarios, compare results with Windows, and capture failures. A successful build or synthetic tests do not demonstrate real-device reliability or repair safety.

No redistribution until third-party licensing is reviewed. Performance and driver diagnostics and all repair actions are later stages.
