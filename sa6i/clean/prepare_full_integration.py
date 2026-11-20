#!/usr/bin/env python3
"""Prepare the exact full cleaner for a separate integration experiment.

This does not make the app compatible with Windows 7, sandbox it, or make its
cleanup safe. The original source executable and ASAR are never modified.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import struct

SOURCE_SHA = 'a7b799c09a4748233095803d36d6453c43faed40ddf4d9d972a376884c1aadc7'
ASAR_SHA = '498f73db929e0c3564148ea93e59f28aeab0694642b639285bd4576b83f60112'
OUTPUT_SHA = '04f2c19923f356fa83f7f5a5e7d074ca3df70020e755204ab63c023d5afd70e9'
OUTPUT_NAME = 'Sa6i Clean Integration.exe'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for data in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def prepare(folder):
    source = folder / 'Sa6i Clean.exe'
    asar = folder / 'resources' / 'app.asar'
    output = folder / OUTPUT_NAME
    if sha(source) != SOURCE_SHA or sha(asar) != ASAR_SHA:
        raise ValueError('Full cleaner executable or ASAR does not match the pinned build')
    with source.open('rb') as f:
        header = f.read(512)
    if header[:2] != b'MZ' or len(header) != 512:
        raise ValueError('Invalid executable header')
    pe = struct.unpack_from('<I', header, 0x3c)[0]
    if pe != 120 or header[pe:pe + 4] != b'PE\0\0' or struct.unpack_from('<H', header, pe + 24)[0] != 0x20b:
        raise ValueError('Unexpected executable layout')
    offsets = (pe + 24 + 40, pe + 24 + 48)
    if any(header[offset:offset + 4] != b'\x0a\x00\x00\x00' for offset in offsets):
        raise ValueError('Unexpected operating system or subsystem versions')
    # Exclusive creation preserves any existing file. On failure, remove only
    # the new file this invocation created; do not touch either source file.
    created = False
    try:
        with source.open('rb') as inp, output.open('xb') as out:
            created = True
            shutil.copyfileobj(inp, out, 1024 * 1024)
        with output.open('r+b') as out:
            for offset in offsets:
                out.seek(offset)
                out.write(b'\x06\x00\x01\x00')
        if sha(output) != OUTPUT_SHA:
            raise ValueError('Prepared executable did not match its pinned checksum')
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cleaner_dir', type=Path)
    args = parser.parse_args()
    print('Created', prepare(args.cleaner_dir.resolve()))
    print('Experimental only: cleaning can permanently delete files; Windows 7 compatibility is unverified.')
