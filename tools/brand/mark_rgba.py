#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Rasterise the Sa6i mark into the app's icon format.

`desktop/app/assets/mark/<size>.rgba` holds straight-alpha RGBA, row by row,
top-down, at the ten sizes `desktop/app/src/mark.rs` embeds. This script
reproduces that format from the vector geometry in `assets/brand/sa6i-mark.svg`
so the icon can be regenerated instead of hand-exported.

The format was verified against the shipped art: the stored `512.rgba` is
byte-identical to `assets/brand/icon-512.png` decoded as RGBA, so straight
alpha, top-down, channel order R,G,B,A is what `mark.rs` expects.

Pure standard library on purpose: this runs on a maintainer's machine, not in
CI, and it must not need a Qt, Rust or NumPy install.

    python3 tools/brand/mark_rgba.py --dest assets/brand/mark-rgba
    python3 tools/brand/mark_rgba.py --dest desktop/app/assets/mark   # install
"""

from __future__ import annotations

import argparse
import math
import os
import sys

# ---- The mark, as in assets/brand/sa6i-mark.svg --------------------------
# One continuous spine: bars at y = 18, 48, 78; turns of r = 15 at x = 61 and
# x = 35; stroke 13; a node of r = 6 at the centre. Grid is 96 x 96.
STROKE = 13.0
NODE_R = 6.0
NODE_C = (48.0, 48.0)
SEGMENTS = [
    ("line", 22.0, 18.0, 61.0, 18.0),
    ("arc", 61.0, 33.0, 15.0, -90.0, 90.0),
    ("line", 61.0, 48.0, 35.0, 48.0),
    ("arc", 35.0, 63.0, 15.0, 90.0, 270.0),
    ("line", 35.0, 78.0, 74.0, 78.0),
]
GRID = 96.0

# ---- Brand --------------------------------------------------------------
MIDNIGHT = (0x0B, 0x10, 0x20)
VIOLET = (0x80, 0x65, 0xFF)
CYAN = (0x36, 0xD6, 0xE7)
NODE_INK = (0xF0, 0xF2, 0xFA)

# The mark is drawn inside this fraction of the tile, centred, so the same art
# works at 16 px and at 512 px.
INSET = 0.72

SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256, 512]


def _distance_to_mark(px: float, py: float) -> float:
    """Shortest distance from a point (in 96-grid units) to the spine."""
    best = float("inf")
    for seg in SEGMENTS:
        if seg[0] == "line":
            _, x0, y0, x1, y1 = seg
            dx, dy = x1 - x0, y1 - y0
            length2 = dx * dx + dy * dy
            t = 0.0 if length2 == 0 else ((px - x0) * dx + (py - y0) * dy) / length2
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
            d = math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))
        else:
            _, cx, cy, r, a0, a1 = seg
            angle = math.degrees(math.atan2(py - cy, px - cx))
            span = (a1 - a0) % 360.0
            if (angle - a0) % 360.0 <= span:
                d = abs(math.hypot(px - cx, py - cy) - r)
            else:
                ends = [
                    math.hypot(px - (cx + r * math.cos(math.radians(a))),
                               py - (cy + r * math.sin(math.radians(a))))
                    for a in (a0, a1)
                ]
                d = min(ends)
        if d < best:
            best = d
    return best


def _spine_colour(px: float, py: float) -> tuple[float, float, float]:
    """The violet-to-cyan gradient along the spine's diagonal."""
    t = ((px - 16.0) + (py - 12.0)) / ((80.0 - 16.0) + (84.0 - 12.0))
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return tuple(VIOLET[i] + (CYAN[i] - VIOLET[i]) * t for i in range(3))


def render(size: int, supersample: int = 0) -> bytes:
    """One tile at `size` x `size`: Midnight background, the mark, the node."""
    if supersample <= 0:
        supersample = 4 if size <= 128 else 3
    n = size * supersample
    scale = (size * INSET / GRID)          # 96-grid units per output pixel
    offset = (size - GRID * scale) / 2.0   # centring, in output pixels
    half = STROKE / 2.0
    # Below 32 px the node would eat the middle bar, so the spine carries the
    # mark alone: the node is a detail, not the letter.
    node_r = NODE_R if size >= 32 else 0.0

    # Accumulate supersampled coverage per output pixel.
    acc = [[0.0, 0.0, 0.0, 0.0] for _ in range(size * size)]
    step = 1.0 / supersample
    for sy in range(n):
        py_out = (sy + 0.5) * step
        gy = (py_out - offset) / scale
        row = (sy // supersample) * size
        for sx in range(n):
            px_out = (sx + 0.5) * step
            gx = (px_out - offset) / scale
            i = row + (sx // supersample)

            cs = half + 0.5 - _distance_to_mark(gx, gy)
            ci = node_r + 0.5 - math.hypot(gx - NODE_C[0], gy - NODE_C[1])
            if cs <= 0.0 and ci <= 0.0:
                continue
            cs = 0.0 if cs < 0.0 else (1.0 if cs > 1.0 else cs)
            ci = 0.0 if ci < 0.0 else (1.0 if ci > 1.0 else ci)

            # Premultiplied: the ink node composited over the gradient spine.
            if cs > 0.0:
                sr, sg, sb = _spine_colour(gx, gy)
            else:
                sr = sg = sb = 0.0
            keep = 1.0 - ci
            cell = acc[i]
            cell[0] += NODE_INK[0] * ci + sr * cs * keep
            cell[1] += NODE_INK[1] * ci + sg * cs * keep
            cell[2] += NODE_INK[2] * ci + sb * cs * keep
            cell[3] += ci + cs * keep

    samples = float(supersample * supersample)
    out = bytearray(size * size * 4)
    for i, cell in enumerate(acc):
        # The tile is opaque Midnight: the premultiplied mark composited over it.
        a = cell[3] / samples
        r = cell[0] / samples + MIDNIGHT[0] * (1.0 - a)
        g = cell[1] / samples + MIDNIGHT[1] * (1.0 - a)
        b = cell[2] / samples + MIDNIGHT[2] * (1.0 - a)
        o = i * 4
        out[o] = int(r + 0.5)
        out[o + 1] = int(g + 0.5)
        out[o + 2] = int(b + 0.5)
        out[o + 3] = 255
    return bytes(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", required=True,
                        help="output directory (assets/brand/mark-rgba to stage, "
                             "desktop/app/assets/mark to install)")
    parser.add_argument("--size", type=int, action="append",
                        help="only this size (repeatable); default: all ten")
    parser.add_argument("--check", action="store_true",
                        help="compare against the files already there instead of writing")
    args = parser.parse_args(argv)

    os.makedirs(args.dest, exist_ok=True)
    sizes = args.size or SIZES
    stale = 0
    for size in sizes:
        data = render(size)
        assert len(data) == size * size * 4, size
        path = os.path.join(args.dest, f"{size}.rgba")
        if args.check:
            try:
                with open(path, "rb") as f:
                    same = f.read() == data
            except FileNotFoundError:
                same = False
            if not same:
                print(f"{path}: differs from the vector mark")
                stale += 1
        else:
            with open(path, "wb") as f:
                f.write(data)
            print(f"wrote {path} ({size}x{size}, {len(data)} bytes)")
    if args.check:
        if stale:
            print(f"{stale} file(s) out of date; run without --check to regenerate")
            return 1
        print("the stored mark matches the vector")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
