# The Sa6i marks

Two supplied logos, both violet-to-blue on black:

- **Sa6i Link** — the laptop, the phone and the swap arrows inside the swoosh,
  with the "Sa6i Link" wordmark. `logo.png` is the full lockup; `icon-256.png`
  and `icon-512.png` are the square app icon built from the emblem alone.
- **Sa6i Clean** — the bin and broom with sparkles. `logo-sa6i-clean.png` is the
  full lockup; the cleaner's own `sa6i/clean/assets/icon-*.png` are the square
  icon built from that emblem.

| File | What it is |
|---|---|
| `logo.png` | The Sa6i Link lockup (emblem and wordmark), as supplied |
| `icon-256.png`, `icon-512.png` | The Sa6i Link app icon |
| `logo-sa6i-clean.png` | The Sa6i Clean lockup, as supplied |

## The ecosystem mark (connected S)

`sa6i-mark.svg` and `sa6i-mark-mono.svg` are the proposed mark for the Sa6i
ecosystem shell: one continuous spine, two turns, one node. It is a vector
proposal and is **not** wired into the app icon yet — see
`docs/design/SIGNAL-THEME.md`. When it is adopted, regenerate
`desktop/app/assets/mark/<size>.rgba` from it and re-run the icon pipeline; do
not replace individual PNGs by hand.

The desktop app does not redraw the mark: `desktop/app/assets/mark/<size>.rgba`
holds the icon art at every size the executable, tray, taskbar and notifications
use, and `desktop/app/src/mark.rs` reduces it for any other size. Regenerate
those files from `icon-512.png` when the artwork changes.
