# Stage D — Brand and UI system: the Signal theme

Status: **applied in M0** — `themes.signal` is in `docs/design/tokens.json`,
validated and generated for both apps, and selectable on the desktop. What is
still open: the default-theme decision, Manrope/JetBrains Mono, the Android
picker, and the app icon. See [M0 report](../plan/M0-REPORT.md).

The repository already has a working design system, and this document extends it
rather than replacing it:

| Existing | What it is | Status |
| --- | --- | --- |
| `docs/design/tokens.json` | Source of truth: colour roles, type, shape, motion, layout | **verified** — consumed by `cargo xtask tokens` |
| `cargo xtask tokens [--check]` | Generates `desktop/app/qml/Tokens.qml` and Android `ui/theme/Tokens.kt`; CI fails if stale | **verified** |
| `validate()` in `tools/xtask/src/main.rs` | Rejects malformed palettes and any role pair below WCAG AA 4.5:1 | **verified** |
| `assets/fonts/` | OFL fonts compiled into both apps | **verified** |
| Themes `bloom`, `hive`, `graphite` | User-selectable; Material You dynamic colour in Bloom | **verified** |

Consequences that follow from that reality:

- A new theme is **not** a new design system; it is a new entry in an existing,
  validated schema. The desktop reads the whole token file as data, so a theme
  reaches QML for free.
- Android does **not**: `render_kotlin()` emits `bloomSeeds`, `graphitePaper/Slate`
  and `hiveWax/Comb` by name, and `validate()` only checks the fixed-palette
  themes it is told about (`["graphite", "hive"]`). Adding a theme therefore
  requires two generator edits plus regeneration — otherwise the theme is
  unreachable on Android *and* unvalidated. This is a real task, not a footnote.
- The existing fonts stay. Signal is a theme, not a coup.

---

## 1. The mark

The ecosystem mark is a **geometric connected-S**: one continuous spine that
turns twice and carries a single node at its centre. It is the letter, the loop
and the link at once — no brain, no circuit pattern, no gradient glow.

```
M22 18 H61 A15 15 0 0 1 61 48 H35 A15 15 0 0 0 35 78 H74
stroke-width 13, round cap/join, bars at y=18/48/78, turns of r=15 at x=61 and x=35
node: circle at (48,48) r=6, Soft White
```

Files: `assets/brand/sa6i-mark.svg` (violet→cyan spine), `assets/brand/sa6i-mark-mono.svg`
(`currentColor`, for trays, watermarks and single-colour printing), preview at
`docs/design/sa6i-mark-preview.png`.

Construction rules: the mark is drawn on a 96×96 grid and always scaled in
proportion; clear space is one stroke width (13/96 ≈ 0.135 of the mark's height)
on all sides; minimum size 16 px (below that use `icon-256.png`-style artwork,
not the SVG); on dark surfaces use the gradient version, on light surfaces the
mono version in Midnight; never recolour the spine to a warning or error colour.

**Wordmark: unchanged.** `assets/brand/logo.png` is the supplied Sa6i lockup and
is not redrawn, re-tracked or re-kerned by us. The new mark accompanies it; it
does not replace the lettering.

**Relationship to the shipped icon.** The icon inside `Sa6i Link.exe`, the tray
and the shortcut is `assets/brand/icon-512.png` (laptop, phone and swap arrows),
compiled from `desktop/app/assets/mark/<size>.rgba` via `src/mark.rs`. The
connected-S is the *ecosystem* mark for the new shell. It replaces the app icon
only after Stage F approval, and when it does it goes through the same pipeline
(regenerate the `.rgba` set, then the installer, then the shortcut) — not by
dropping an SVG into a resources folder.

## 2. Colour

Brand constants from the brief, and what each one is allowed to do:

| Token | Hex | Allowed for | Not allowed for |
| --- | --- | --- | --- |
| Midnight | `#0B1020` | Dark surface base, on-primary text | Any text on a dark surface |
| Deep Navy | `#131C32` | Raised surfaces, card fills | Text |
| Electric Violet | `#8065FF` | Brand fills, focus rings, active rail, chart series 1 | **Text** — 4.71:1 on Midnight, 4.21:1 on Deep Navy |
| Signal Cyan | `#36D6E7` | Data accents, "live" indicators, chart series 2 | Body text (fine as text on Midnight at 10.75:1, but it reads as a signal, so it stays on data) |
| Soft White | `#F0F2FA` | Primary text on dark, mono mark | — |
| Muted Slate | `#8793AA` | Secondary text on dark (6.12:1) | Small text on light surfaces |

That Violet line is the important one: at 4.71:1 it fails AA on Deep Navy, so it
cannot be the `primary` role the app uses for text and icons. The theme maps the
brand to lighter/darker accessible variants instead:

**`signal.midnight`** (dark)

```json
{
  "surface": "#0B1020",
  "surfaceContainerLow": "#0E1426",
  "surfaceContainer": "#131C32",
  "surfaceContainerHigh": "#18223C",
  "surfaceContainerHighest": "#1E2946",
  "onSurface": "#F0F2FA",
  "onSurfaceVariant": "#AAB5CC",
  "outline": "#6C7893",
  "outlineVariant": "#2A3654",
  "primary": "#B3A0FF",
  "onPrimary": "#1A0F45",
  "primaryContainer": "#33246E",
  "onPrimaryContainer": "#E6DEFF",
  "secondaryContainer": "#123A45",
  "onSecondaryContainer": "#BFEDF5",
  "warning": "#F2C14E",
  "error": "#FFA9A2",
  "onError": "#3B0B07"
}
```

**`signal.daylight`** (light)

```json
{
  "surface": "#F7F8FC",
  "surfaceContainerLow": "#F1F3F9",
  "surfaceContainer": "#E9ECF5",
  "surfaceContainerHigh": "#E1E5F0",
  "surfaceContainerHighest": "#D9DEEB",
  "onSurface": "#131C32",
  "onSurfaceVariant": "#485470",
  "outline": "#68748F",
  "outlineVariant": "#C3CBDB",
  "primary": "#5335C8",
  "onPrimary": "#FFFFFF",
  "primaryContainer": "#E4DCFF",
  "onPrimaryContainer": "#1E0F4D",
  "secondaryContainer": "#CDEDF4",
  "onSecondaryContainer": "#05303A",
  "warning": "#7A5000",
  "error": "#B3261E",
  "onError": "#FFFFFF"
}
```

Both palettes were checked against the same rules `validate()` enforces — every
required role present, and every pair of `onSurface`/`onSurfaceVariant`/`primary`/
`warning`/`error` against all five surfaces at ≥ 4.5:1. Tightest margins: midnight
6.43:1 (`primary` on `surfaceContainerHighest`), daylight 4.86:1 (`error` on
`surfaceContainerHighest`). `#8065FF` and `#36D6E7` are kept out of the role
table as **brand fills** (`brand.accent`, `brand.signal`) where the 4.5:1 rule
does not apply — charts, focus rings, the active rail node, hairlines at ≥ 3:1.

No green anywhere, matching the existing principle: success and connected states
use `primary` and `primaryContainer`, never traffic-light green.

## 3. Type

| Use | Family | Why |
| --- | --- | --- |
| UI, headings | **Manrope** (variable, 200–800) | Slightly technical grotesque, holds up at 12 px, pairs with the geometric mark; the brief's first choice after Inter |
| Numbers, IDs, codes, metric values | **JetBrains Mono** | True tabular figures — a CPU percentage that shifts width on every refresh is a bug you can see |
| Legacy themes | Figtree, Instrument Serif, Space Mono | Unchanged, still bundled |

Manrope is used with `font-variant-numeric: tabular-nums`-equivalent (Qt: font
features `tnum`); percentage and byte values are right-aligned and never animate
their digit width. Sizes reuse the existing scale (`displayLarge` 44 → `caption` 11);
only `displaySmall` drops 30 → 28 in Signal so long module names fit the rail.

Fonts are OFL and already have a pipeline (`assets/fonts/` + `desktop/app/build.rs` +
Android assets). Adding two families costs ~2 files, ~700 KB, and a `notices`
regeneration — not a new mechanism.

## 4. The Spine — the one distinctive idea

Every dashboard has a sidebar. Sa6i should not have another one.

The shell's navigation is the mark, unrolled: a vertical spine that runs down the
left edge, turning twice exactly as the glyph does, with the six modules as
stations on it. The active station sits at a turn (that is where the light goes).
The spine is one 1 px path plus six 8 px nodes — it draws in ~300 ms on launch,
and only then is it interactive. Connection state lives on the spine, not in a
corner chip: when no phone is paired the spine above Link is drawn dashed.

The DETECT → UNDERSTAND → RECOMMEND → EXECUTE → VERIFY loop is **not** a wizard.
It is the fixed five-step track printed on every finding card and every action
sheet; the current step is lit, completed steps are filled, and VERIFY is the
step most products omit — ours is always visible, because a fix that was not
verified is a claim, not a fix.

## 5. Data display rules

| Element | Rule |
| --- | --- |
| Metric tile | value, unit, sparkline of the last 60 samples, one 11 px delta chip (`+4.2%`), and the sample timestamp |
| Sparkline | 1.5 px line, no fill, no gradient; a gap in samples is a gap in the line, never a straight interpolated segment |
| Unavailable metric | dashed baseline, hatched block, text "Not available on this system", reason on hover. **Never `0`, never a fake curve** |
| Gauge | only for bounded things (disk used, memory used); never for CPU, which has no meaningful maximum |
| Severity | `Info` Slate, `Notice` Primary, `Warning` `warning`, `Critical` `error`; always paired with an icon and a word, never colour alone |
| Evidence | when the user asks "why?", show the metric path, the window, the threshold, and the sample ids — the actual numbers, not a paraphrase |

## 6. Components to add (new, on top of the existing set)

`MetricTile`, `Sparkline`, `EvidenceDrawer`, `FindingCard` (with the loop track),
`ActionSheet` (what will happen, what changed after, rollback if any),
`AuditRow`, `ProviderBadge` ("On this PC / Cloud / Rules only"), `UnknownBlock`.

Each is defined by tokens only — no hard-coded colours — so all four themes keep
working, which is the existing contract.

## 7. Windows 7 vs Windows 10/11

| | Windows 10/11 | Windows 7 (degraded) |
| --- | --- | --- |
| Surfaces | opaque `surfaceContainer` over `surface`; optional 1 px 8% violet top hairline | same, no blur, no translucency, no acrylic |
| Backdrop | Spine draw-in animation, sparkline motion | animation only if not in a remote/RDP session; otherwise static |
| Shadows | none inside content areas, one window shadow | flat, 1 px `outlineVariant` borders only |
| Motion | springs from `tokens.json` | 120 ms fades only |
| Rounded corners | 8–16 px | 2–4 px where the platform looks wrong otherwise |
| Missing telemetry | GPU, per-disk counters full | GPU `Unsupported`; `MSFT_PhysicalDisk` and GPU PDH are Win8+/Win10+ |

Rule: Win7 is a *degraded target*. It renders correctly and tells the truth about
what it cannot measure; it is not a second visual design.

## 8. Accessibility

Focus ring is 2 px `primary` with a 1 px `surface` inset, always visible on
keyboard focus. Motion respects the reduced-motion switch. Hit targets ≥ 32 px
desktop / 44 px touch. `UnknownBlock` and severity always carry text. Numbers are
monospaced and right-aligned so columns can be read down.

## 9. What applying this cost

Done in M0 (see the [M0 report](../plan/M0-REPORT.md) for evidence):

1. `tokens.json`: `themes.signal` with `variants.midnight` / `.daylight`,
   `brand`, `shape`, `label`, `rules`, `fonts`.
2. `validate()`: `"signal"` added to the fixed-palette list, so the new palettes
   are contrast-checked like the others.
3. `render_kotlin()`: emits `signalMidnight` / `signalDaylight`.
4. `Tokens.qml` and `Tokens.kt` regenerated (the generator is authoritative).
5. `Theme.qml`: a `signal` branch for palette, status, cards, tiles, rail, shape
   and label; `settings.rs` and `prefs.rs` know the name; Settings offers it.
6. `tools/brand/mark_rgba.py` rasterises the mark to the ten icon sizes;
   `assets/brand/mark-rgba/` is staged.

Still open: Manrope and JetBrains Mono (needs the font pipeline plus a `notices`
regeneration), the Android picker, whether Signal becomes the default, and
swapping the app icon.
