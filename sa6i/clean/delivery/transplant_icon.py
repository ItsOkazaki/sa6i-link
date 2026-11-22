"""Prototype of the icon transplant, used to validate the resource walk.

Runs here, against any PE file, to prove the offsets and the fit rules before
the same steps are written for the patch script. Prints what it would change
and never writes unless --write is given.
"""

from __future__ import annotations

import argparse
import struct
import sys


class PE:
    def __init__(self, data: bytearray):
        self.data = data
        if data[:2] != b'MZ':
            raise SystemExit('not a PE file: no MZ signature')
        self.pe = struct.unpack_from('<I', data, 0x3C)[0]
        if data[self.pe:self.pe + 4] != b'PE\0\0':
            raise SystemExit('not a PE file: no PE signature')
        coff = self.pe + 4
        self.sections = struct.unpack_from('<H', data, coff + 2)[0]
        opt_size = struct.unpack_from('<H', data, coff + 16)[0]
        optional = coff + 20
        magic = struct.unpack_from('<H', data, optional)[0]
        self.is64 = magic == 0x20B
        dirs = optional + (112 if self.is64 else 96)
        self.rsrc_rva, self.rsrc_size = struct.unpack_from('<II', data, dirs + 2 * 8)
        table = optional + opt_size
        self.section_table = []
        for index in range(self.sections):
            base = table + index * 40
            name = data[base:base + 8].rstrip(b'\0').decode('latin-1')
            vsize, vaddr, rawsize, rawptr = struct.unpack_from('<IIII', data, base + 8)
            self.section_table.append((name, vaddr, vsize, rawptr, rawsize))

    def offset(self, rva: int) -> int:
        for _, vaddr, vsize, rawptr, rawsize in self.section_table:
            span = max(vsize, rawsize)
            if vaddr <= rva < vaddr + span:
                return rawptr + (rva - vaddr)
        raise SystemExit(f'rva {rva:#x} is not inside any section')

    def entries(self, directory_offset: int):
        named, ids = struct.unpack_from('<HH', self.data, directory_offset + 12)
        for index in range(named + ids):
            base = directory_offset + 16 + index * 8
            name, target = struct.unpack_from('<II', self.data, base)
            yield name, target

    def find(self, type_id: int, name_id: int | None = None):
        """Every leaf of the resource tree below ``type_id``."""
        root = self.offset(self.rsrc_rva)
        out = []
        for name, target in self.entries(root):
            if name != type_id or not target & 0x80000000:
                continue
            level1 = root + (target & 0x7FFFFFFF)
            for name2, target2 in self.entries(level1):
                if name_id is not None and name2 != name_id:
                    continue
                if not target2 & 0x80000000:
                    continue
                level2 = root + (target2 & 0x7FFFFFFF)
                for name3, target3 in self.entries(level2):
                    if target3 & 0x80000000:
                        continue
                    leaf = root + target3
                    rva, size, _, _ = struct.unpack_from('<IIII', self.data, leaf)
                    out.append({
                        'name': name2,
                        'size_offset': leaf + 4,
                        'rva': rva,
                        'size': size,
                        'offset': self.offset(rva),
                    })
        return out


def read_ico(path):
    data = open(path, 'rb').read()
    _, kind, count = struct.unpack('<HHH', data[:6])
    if kind != 1:
        raise SystemExit('not an icon file')
    out = []
    for index in range(count):
        w, h, _, _, _, bpp, size, off = struct.unpack('<BBBBHHII', data[6 + index * 16:22 + index * 16])
        out.append({
            'size': w or 256,
            'bytes': data[off:off + size],
            'png': data[off:off + 8] == b'\x89PNG\r\n\x1a\n',
        })
    return out


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('exe')
    parser.add_argument('ico')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args(argv)

    data = bytearray(open(args.exe, 'rb').read())
    pe = PE(data)
    icons = read_ico(args.ico)
    print(f'resource directory at rva {pe.rsrc_rva:#x}, {pe.rsrc_size} bytes, {len(pe.section_table)} sections')
    print('sections:', ', '.join(s[0] for s in pe.section_table))

    images = {entry['name']: entry for entry in pe.find(3)}
    print(f'RT_ICON images: {len(images)}, ids {sorted(images)[:12]}{" ..." if len(images) > 12 else ""}')

    groups = pe.find(14)
    print(f'RT_GROUP_ICON groups: {len(groups)}')
    if not groups:
        raise SystemExit('no group icons: nothing to replace')

    changed = 0
    for group in groups:
        base = group['offset']
        _, _, count = struct.unpack_from('<HHH', data, base)
        print(f"  group {group['name']} at {base:#x}: {count} images")
        for index in range(count):
            entry = base + 6 + index * 14
            w, h, colours, reserved, planes, bpp, payload, icon_id = struct.unpack_from('<BBBBHHIH', data, entry)
            size = w or 256
            slot = images.get(icon_id)
            if slot is None:
                print(f'    {size}x{size}: id {icon_id} missing')
                continue
            candidates = [c for c in icons if c['size'] == size and len(c['bytes']) <= slot['size']]
            candidates.sort(key=lambda c: len(c['bytes']))
            if not candidates:
                print(f'    {size}x{size}: id {icon_id} slot {slot["size"]} bytes, nothing fits')
                continue
            pick = candidates[0]
            print(f'    {size}x{size}: id {icon_id} slot {slot["size"]} -> '
                  f'{"PNG" if pick["png"] else "DIB"} {len(pick["bytes"])} bytes')
            if args.write:
                data[slot['offset']:slot['offset'] + len(pick['bytes'])] = pick['bytes']
                tail = slot['offset'] + len(pick['bytes'])
                data[tail:slot['offset'] + slot['size']] = b'\0' * (slot['size'] - len(pick['bytes']))
                struct.pack_into('<I', data, slot['size_offset'], len(pick['bytes']))
                struct.pack_into('<I', data, entry + 8, len(pick['bytes']))
                changed += 1

    if args.write:
        open(args.exe + '.icon-patched', 'wb').write(bytes(data))
        print(f'wrote {args.exe}.icon-patched, {changed} images replaced')
        again = PE(bytearray(open(args.exe + '.icon-patched', 'rb').read()))
        print('re-parse ok:', len(again.find(14)), 'groups,', len(again.find(3)), 'images')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
