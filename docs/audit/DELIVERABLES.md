# Stage A–E deliverables: index and status

The fifteen required artefacts, where each one lives, and its honest state.
Status: **done** · **partial** · **open**.

| # | Deliverable | Where | Status | Note |
| --- | --- | --- | --- | --- |
| 1 | Repository audit | [STAGE-A-AUDIT.md](STAGE-A-AUDIT.md) | done | stack, LOC, tests, CI, ADRs |
| 2 | Feature status matrix | [STAGE-A-AUDIT.md](STAGE-A-AUDIT.md) | done | every feature tagged verified/partial/absent |
| 3 | Open-source research | [STAGE-B-RESEARCH.md](STAGE-B-RESEARCH.md) | done | verified licences, not recall |
| 4 | Licensing and compatibility | [STAGE-B-RESEARCH.md](STAGE-B-RESEARCH.md), `deny.toml` | done | GPL/MPL direction encoded in CI |
| 5 | Architecture | [../architecture/INTELLIGENCE-CORE.md](../architecture/INTELLIGENCE-CORE.md) | done | contracts only, no product code |
| 6 | Module dependency diagram | [../architecture/MODULE-MAP.md](../architecture/MODULE-MAP.md) | done | plus the eight dependency rules |
| 7 | Shared data model | INTELLIGENCE-CORE §4 | done | `MetricState`, `Snapshot`, `Finding`, `Evidence` |
| 8 | AI intelligence architecture | INTELLIGENCE-CORE §7 | done | deterministic core, model as explainer |
| 9 | Visual identity and design system | [../design/SIGNAL-THEME.md](../design/SIGNAL-THEME.md) | done, **not applied** | extends `tokens.json`; no generator edits yet |
| 10 | Screen inventory | [../design/SCREEN-INVENTORY.md](../design/SCREEN-INVENTORY.md) | done | 15 new screens, states and gaps |
| 11 | Security and permission model | [../architecture/SECURITY-MODEL.md](../architecture/SECURITY-MODEL.md) | done | includes three live exposures (keystore) |
| 12 | Testing strategy | [../plan/STAGE-E-PLAN.md](../plan/STAGE-E-PLAN.md) §1 | done | fixtures as the price of a rule |
| 13 | Prioritised roadmap | STAGE-E-PLAN §2 | done | M0–M5 with exit criteria |
| 14 | Risk assessment | STAGE-E-PLAN §3 | done | R1–R12 |
| 15 | Competition demo scenario | STAGE-E-PLAN §4 | done | 3 minutes, offline, real data |

## Open items carried into Stage F

1. **Brand merge decision.** Signal is proposed as a fourth theme alongside
   Bloom/Hive/Graphite, default on the desktop. Alternatives: replace Bloom, or
   ship Signal only in the new ecosystem shell. Needs your call before M0.
2. **Manrope + JetBrains Mono** replace Figtree/Space Mono in Signal only, or
   across all themes. Fonts are OFL either way; the cost is ~700 KB and a notices
   regeneration.
3. **Android reach of the new theme** requires `render_kotlin()` changes; do it in
   M0 or defer to the phone-side milestone.
4. **Signing key exposure** ([SECURITY-MODEL](../architecture/SECURITY-MODEL.md) §7)
   is real today and is the first M0 task regardless of everything else.
5. **Icon swap** (connected-S over the current laptop/phone icon) is a Stage F
   decision, not a design detail — it changes what users see on their desktop.

## Approval gate

Implementation begins at **M0** only on explicit approval of Stages A–E. Until
then this repository contains documentation, one SVG mark and one preview PNG —
no product code, no token changes, no generator edits.
