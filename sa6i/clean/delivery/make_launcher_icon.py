"""Build the icon that replaces the original product's icon in the launcher.

The launcher's icon lives in the executable's resource section, not in any
string, so it is replaced by transplanting ICO entries into the existing
RT_ICON slots. That only works when the new entry is no larger than the slot it
lands in, and the entries have to carry the same pixel size as the slot, so
this writes every common size in two encodings: an uncompressed DIB, which
every Windows since 95 draws, and a PNG, which is far smaller but only reliable
at 256 px and above.

The script that does the transplant picks, per slot, the smallest entry whose
size matches the slot and which fits.

Usage::

    python sa6i/clean/delivery/make_launcher_icon.py \
        --source assets/brand/icon-512.png \
        --out sa6i/clean/delivery/Sa6i-Link-Icon.ico
"""

from __future__ import annotations

import argparse
import io
import pathlib
import struct
import sys

from PIL import Image

#: Pixel sizes worth carrying: Explorer and the taskbar ask for 16, 20, 24 and
#: 32, alt-tab and large-icon views for 48 and 64, and 256 for thumbnails.
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def dib_payload(image: Image.Image, size: int) -> bytes:
    """One uncompressed 32-bit icon image, as Windows stores it in an ICO."""
    scaled = image.resize((size, size), Image.LANCZOS).convert('RGBA')
    pixels = scaled.load()

    rows = bytearray()
    for y in range(size - 1, -1, -1):
        for x in range(size):
            red, green, blue, alpha = pixels[x, y]
            rows += bytes((blue, green, red, alpha))

    # 1 bit per pixel, rows padded to four bytes: transparent pixels are 1.
    mask_stride = ((size + 31) // 32) * 4
    mask = bytearray()
    for y in range(size - 1, -1, -1):
        row = bytearray(mask_stride)
        for x in range(size):
            if pixels[x, y][3] < 128:
                row[x >> 3] |= 0x80 >> (x & 7)
        mask += row

    header = struct.pack(
        '<IiiHHIIiiII',
        40,            # header size
        size,          # width
        size * 2,      # height: colour image plus mask
        1,             # planes
        32,            # bits per pixel
        0,             # no compression
        len(rows) + len(mask),
        0, 0, 0, 0,
    )
    return header + bytes(rows) + bytes(mask)


def png_payload(image: Image.Image, size: int) -> bytes:
    buffer = io.BytesIO()
    image.resize((size, size), Image.LANCZOS).convert('RGBA').save(
        buffer, format='PNG', optimize=True
    )
    return buffer.getvalue()


def build_ico(source: pathlib.Path, sizes=SIZES) -> bytes:
    image = Image.open(source)
    image.load()
    image = image.convert('RGBA')

    entries: list[tuple[int, bytes]] = []
    for size in sizes:
        entries.append((size, dib_payload(image, size)))
        if size >= 128:
            # A PNG copy too: if a slot is too small for the DIB, this fits.
            entries.append((size, png_payload(image, size)))

    header = struct.pack('<HHH', 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory = bytearray()
    blobs = bytearray()
    for size, data in entries:
        directory += struct.pack(
            '<BBBBHHII',
            size % 256,      # 0 means 256
            size % 256,
            0,               # palette colours
            0,               # reserved
            1,               # planes
            32,              # bits per pixel
            len(data),
            offset,
        )
        blobs += data
        offset += len(data)
    return header + bytes(directory) + bytes(blobs)


def describe(data: bytes) -> list[str]:
    _, kind, count = struct.unpack('<HHH', data[:6])
    if kind != 1:
        raise SystemExit('not an icon file')
    lines = []
    for index in range(count):
        width, height, _, _, _, bpp, size, off = struct.unpack(
            '<BBBBHHII', data[6 + index * 16:22 + index * 16]
        )
        flavour = 'PNG' if data[off:off + 8] == b'\x89PNG\r\n\x1a\n' else 'DIB'
        lines.append(f'{width or 256}x{height or 256} {bpp}bpp {flavour} {size} bytes')
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=pathlib.Path, default=pathlib.Path('assets/brand/icon-512.png'))
    parser.add_argument('--out', type=pathlib.Path, required=True)
    args = parser.parse_args(argv)

    data = build_ico(args.source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    print(f'wrote {args.out} ({len(data)} bytes)')
    for line in describe(data):
        print('  ' + line)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
