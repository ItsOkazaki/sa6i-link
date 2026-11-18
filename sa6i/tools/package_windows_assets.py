#!/usr/bin/env python3
"""Make a separate portable-package candidate with two replacement artwork files.

This is locked to the exact publicly distributed ZIP and does not modify the
input, executables, DLLs, manifest, licenses, or other resources. It is not a
Windows runtime test and does not modify a registered/signed MSIX package.
"""
import hashlib
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ZIP = '4cfcb2227ba61f6d54282dfb2513ae9c8dda5faceda2ce11979e4a4237f602d9'
ASSETS = {
    'Sa6i-Link/Assets/Square150x150Logo.png': ('Square150x150Logo.png', 'ee9b76dd83c8afc3ff05d4347ccd83ee3cca355cdc1b2f3d224e10d4771672c8'),
    'Sa6i-Link/Assets/Square44x44Logo.png': ('Square44x44Logo.png', 'a05598cf7a830ed71e8226defe7721ff6e3dc5697958454c1a939e60db7576c6'),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def package(source, destination):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('Input and output must be different files')
    if sha(source.read_bytes()) != EXPECTED_ZIP:
        raise ValueError('Unexpected input ZIP; refusing to modify')
    replacements = {name: (ROOT / 'sa6i/assets/windows' / filename).read_bytes()
                    for name, (filename, _) in ASSETS.items()}
    with ZipFile(source) as src:
        entries = src.infolist()
        names = [e.filename for e in entries]
        if len(names) != len(set(names)) or any(names.count(n) != 1 for n in ASSETS):
            raise ValueError('Missing or duplicate archive entries')
        if src.testzip() is not None:
            raise ValueError('Input ZIP failed integrity check')
        for name, (_, expected) in ASSETS.items():
            if sha(src.read(name)) != expected:
                raise ValueError('Unexpected original asset: ' + name)
        with ZipFile(destination, 'x') as dst:
            dst.comment = src.comment
            for entry in entries:
                dst.writestr(entry, replacements.get(entry.filename, src.read(entry)))
    with ZipFile(source) as src, ZipFile(destination) as dst:
        if dst.testzip() is not None or src.namelist() != dst.namelist():
            raise ValueError('Output ZIP failed integrity check')
        for name in src.namelist():
            expected = replacements[name] if name in replacements else src.read(name)
            if dst.read(name) != expected:
                raise ValueError('Output entry mismatch: ' + name)
    print('Output SHA-256:', sha(destination.read_bytes()))
    print('Changed entries:', ', '.join(ASSETS))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: package_windows_assets.py INPUT.zip OUTPUT.zip')
    package(sys.argv[1], sys.argv[2])
