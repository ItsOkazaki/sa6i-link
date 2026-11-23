# M0 report — hygiene and the Signal theme

Branch `arena/077ce3b0-sa6i-link`. Scope: the four M0 items from
[STAGE-E-PLAN](STAGE-E-PLAN.md) §2. Written before M1, so M1 starts from a
green, branded base.

## What landed

| Item | State | Where |
| --- | --- | --- |
| Signing key custody | **verified, documented, not moved** — see below | [SIGNING-KEY](../operations/SIGNING-KEY.md) |
| Signal theme in the token system | **done** | `docs/design/tokens.json`, `tools/xtask/src/main.rs`, `desktop/app/qml/Tokens.qml`, `android/.../Tokens.kt` |
| Signal selectable in the app | **done** | `Theme.qml`, `settings.rs`, `bridge/prefs.rs`, `bridge/app.rs`, `SettingsPage.qml` |
| Mark rasteriser | **done, staged** | `tools/brand/mark_rgba.py`, `assets/brand/mark-rgba/` |
| App icon replaced | **deliberately not done** — open decision | — |
| Manrope + JetBrains Mono | **deferred** — see "Not done" | — |

### The key

The premise from Stage A was wrong in one respect and I checked it rather than
repeating it: the keystore is **not** public. On 2026-11-16 the Drive API showed
one permission on each of `PRIVATE - Sa6i Link Android release keystore.p12` and
its password file — the owner, with no `anyoneWithLink` grant and no shared
parent folder. What is public-by-link is the *build distribution* (the candidate
and branding ZIPs carry an `anyone` reader grant), which is a provenance problem,
not a key-leak problem.

So the work is custody, not incident response. [SIGNING-KEY](../operations/SIGNING-KEY.md)
records the verified facts, the 15-minute hardening sequence (2FA review →
encrypted archive → fingerprints → two copies → remove the plaintext password
from Drive → CI secrets), the fingerprint table to fill in, and the rotation
decision tree, including why rotation is the *expensive* option for sideloaded
builds. I did not move or delete anything in Drive: the procedure changes where
the key lives, and that is a human step with a paper trail.

### The theme

`themes.signal` is a fourth entry in the existing schema, not a new system:
`variants.midnight` and `variants.daylight`, brand constants under `brand`,
geometric shape scale, and `rules` documenting the constraints a reader needs
(no green, violet is never text, `Unknown` is never zero).

Both palettes pass the generator's own rules. I ported `validate()` and
`check_palette()`/`check_contrast()` from `tools/xtask/src/main.rs` to Python
line for line and ran them over the whole file including the new theme: five
seeds × two modes, plus the fixed themes `graphite`, `hive` and now `signal`.
Tightest margins are 6.43:1 (`primary` on `surfaceContainerHighest`, midnight)
and 4.86:1 (`error` on `surfaceContainerHighest`, daylight), both above the
4.5:1 floor the validator enforces.

The generator change is two additions in `render_kotlin()` (the Android theme
file would otherwise be blind to the theme) and `"signal"` in the fixed-palette
list in `validate()` (otherwise the new palettes would be the only unvalidated
ones in the file).

In the app, Signal is a **selectable** theme; the default is still Bloom. Making
it the default is a one-line change (`#[default]` on the enum variant) and is
open question 1 from the approval gate, so it stays a decision rather than a
surprise.

### The mark

`tools/brand/mark_rgba.py` rasterises the vector mark into the ten sizes
`desktop/app/src/mark.rs` embeds. It is standard-library Python, so it needs no
Qt, Rust or NumPy.

Two facts make it trustworthy rather than hopeful:

1. The output format was **verified against the shipped art**: `512.rgba` is
   byte-identical to `assets/brand/icon-512.png` decoded as straight-alpha RGBA,
   top-down (mean absolute difference 0.0 for RGBA, 10.4 for BGRA, 21.0 flipped).
   The tool writes exactly that.
2. It is **self-checking**: `--check` recomputes and compares, and reports
   "the stored mark matches the vector".

Output is staged in `assets/brand/mark-rgba/`; `desktop/app/assets/mark/` is
untouched, because swapping the desktop icon is open question 4. Installing is:

```
python3 tools/brand/mark_rgba.py --dest desktop/app/assets/mark
```

then rebuild, as `build.rs` turns those files into the executable's `.ico`.
Below 32 px the node is dropped (it eats the middle bar at 16 px) and the spine
carries the letter alone.

## How each claim was checked

| Claim | Method |
| --- | --- |
| `tokens.json` edit is additive | unified diff: 83 added lines, 0 removed |
| The palettes satisfy WCAG AA per the project's rules | Python port of `validate()`, same algorithm and same 4.5:1 floor |
| Generated QML/Kotlin match the Rust generator | A Python mirror of `render_qml()`/`render_kotlin()` reproduces the **previously committed** files byte-for-byte before being applied to the new tokens |
| `Tokens.qml` is valid data | extracted the object literal and parsed it as JSON; `themes.signal` carries `variants`, `shape`, `label`, `brand` |
| The QML edits are structurally intact | delimiter counts identical per file (the flattening of two ternaries removes three paren pairs; the picker entry adds one pair) |
| The icon format matches the shipped art | byte comparison against `icon-512.png` (above) |
| The rasteriser is deterministic | `--check` after regeneration: identical |

## What I could not verify here — run these first

This sandbox has **no Rust toolchain and no Qt**, so nothing compiled or ran.
The Rust and QML edits are written to mirror existing patterns exactly, but CI on
a machine with the toolchain is the real gate:

```powershell
cargo xtask tokens --check          # must print "generated theme files are up to date"
cargo test -p xtask                 # validator + generator tests, now covering signal
cargo fmt --check
cargo clippy --workspace --all-targets -- -D warnings
cargo check -p sa6i-link            # the desktop app: exhaustive Theme matches
```

If `cargo xtask tokens` reports a difference, run it without `--check` and commit
the regenerated files: the generator is authoritative, not my mirror.

Then launch the app, Settings → Appearance → pick **Signal**, and switch
between Dark and Light.

## Not done, and why

- **Default theme.** Open decision (question 1). One line once answered.
- **Manrope + JetBrains Mono.** Adding fonts means `assets/fonts/*.ttf`, their
  OFL files, and a regenerated `notices` file — and `cargo xtask notices` needs
  cargo. Shipping a theme that *declares* fonts the app does not have would make
  the token file lie, so the theme declares the bundled families and carries a
  `$note` recording the pending switch. This is the first task of M1's setup.
- **Android wiring.** `Tokens.kt` now carries `signalMidnight`/`signalDaylight`;
  the Compose theme does not offer the theme in its picker yet. That belongs with
  the phone-side milestone.
- **App icon.** Staged only. See question 4.

## Exit criteria

- [x] Key custody documented; the public-link claim corrected with evidence
- [x] Theme in tokens, validated, generated for both apps, selectable on desktop
- [x] Mark reproducible from vector, format proven against shipped art
- [ ] `cargo xtask tokens --check` green **on a machine with cargo** — needs you
- [ ] App launches and renders each theme — needs you

M1 (telemetry → evidence → Monitor) starts once the two unchecked lines are
green.
