# The Sa6i Link mark

The Sa6i shield: a violet-to-blue shield with a four-point spark on the dark
Sa6i tile. It is the same shield family as the Sa6i Clean icon, so the two
windows read as one product.

| File | What it is |
|---|---|
| `icon.svg` | The full-color app icon: dark tile, gradient shield, spark |
| `icon-flat.svg` | The same without the gradients, for flat contexts |
| `icon-mono.svg` | The mark alone in white, for one-color uses (notifications, themed icons) |
| `icon-512.png` | `icon.svg` at 512 × 512 |

The desktop app draws the mark itself from the same geometry
(`desktop/app/src/mark.rs`): the executable's icon, the tray and notification
icons at every size.

Colors: tile `#1B0D33` to `#0B0516`, tile edge `#3A2A5E`, shield `#9B5CF0` to
`#2F7BFF`, shield edge `#8B6CE8`, spark `#F2EEFF`.
