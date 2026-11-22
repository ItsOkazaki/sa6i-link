#!/usr/bin/env python3
"""Read (never patch) the QML window resource from the known Sa6i Link ZIP."""
import argparse
import hashlib
import struct
import zlib
from pathlib import Path
from zipfile import ZipFile

ZIP_SHA = '18e66fe82dc1fad747e192a2bb0aef3c8fdac8d2398f974a73f4853d16d89d12'
EXE_SHA = 'c168bfcd6b51d3528ea78a6c0d135c9d101b9e839c6785facb5f38f5d109daf5'
QML_SHA = '17be867297035f63edb19f5c60bd9ffdaa9ea4a668bc1e1d877d959c6b6307a4'
EXE_NAME = 'Sa6i.Link/Sa6i-Link/Sa6i Link App.exe'
OFFSET = 0x1D53D2D
CAPACITY = 9317
FALLBACK = '/qt/qml/app/sa6i-link/qml/NainWindow.qml'.encode('utf-16le')


def checksum(value):
    return hashlib.sha256(value).hexdigest()


def extract_qml(exe):
    if checksum(exe) != EXE_SHA:
        raise ValueError('Unknown executable; refusing to inspect at fixed offsets')
    if exe.count(FALLBACK) != 1:
        raise ValueError('Expected source fallback marker not found')
    compressed_with_size, uncompressed = struct.unpack_from('>II', exe, OFFSET - 8)
    size = compressed_with_size - 4
    if not 0 < size <= CAPACITY or uncompressed > 100000:
        raise ValueError('Unexpected resource size')
    content = zlib.decompress(exe[OFFSET:OFFSET + size])
    if len(content) != uncompressed or checksum(content) != QML_SHA:
        raise ValueError('Unexpected resource content')
    return content


def inspect(archive):
    if checksum(archive.read_bytes()) != ZIP_SHA:
        raise ValueError('Unknown archive; refusing to inspect')
    with ZipFile(archive) as z:
        if z.namelist().count(EXE_NAME) != 1:
            raise ValueError('Executable not found exactly once')
        return extract_qml(z.read(EXE_NAME))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path, help='new QML output file; will not overwrite')
    args = parser.parse_args()
    content = inspect(args.archive)
    with args.output.open('xb') as f:
        f.write(content)
    print('Extracted window QML SHA-256:', checksum(content))
