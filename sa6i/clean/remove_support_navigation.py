#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a separate hardened cleaner with only Tip and Feedback navigation removed.

Requires Node.js and npx; verifies the exact tested cleaner inputs. No user
installation is modified. Qt desktop hash pins must match the output files.
"""
import argparse
import hashlib
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
import debrand_cleaner

EXE_SHA = '2c9bdd29209ebc58103753a2a66d8b9c840d94054eea368239566b5d42408d74'
ASAR_SHA = '4cbe981c5a473d61a7b679e61db49b4c5a0a052ba5783ce903054b46562a10ba'
OUTPUT_EXE_SHA = 'c3d9a0949e46792dbf5265c8bf71d7acc6149fc48e07d716b2f1664f6bb47623'
OUTPUT_ASAR_SHA = 'e94b30b5b5507c5ad94f39e2dfb70d91337d6d08ed2beb2b29905655755227bc'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def header_sha(path):
    with path.open('rb') as f:
        _, _, _, size = struct.unpack('<IIII', f.read(16))
        if not 0 < size < 20_000_000:
            raise ValueError('Invalid ASAR header')
        data = f.read(size)
        if len(data) != size:
            raise ValueError('Truncated ASAR header')
        return hashlib.sha256(data).hexdigest().encode('ascii')

def make(exe, asar, output):
    exe, asar, output = Path(exe).resolve(), Path(asar).resolve(), Path(output).absolute()
    if output.exists():
        raise FileExistsError('Output already exists')
    if sha(exe) != EXE_SHA or sha(asar) != ASAR_SHA:
        raise ValueError('Cleaner input hashes do not match the tested hardened build')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.ui-cleaner-') as t:
        temp = Path(t)
        app = temp / 'app'
        subprocess.run(['npx', '--yes', '@electron/asar@3.2.10', 'extract', str(asar), str(app)], check=True)
        bundles = list((app / 'dist/assets').glob('index-*.js'))
        if len(bundles) != 1:
            raise ValueError('Expected one renderer bundle')
        renderer = bundles[0]
        old = renderer.read_text(encoding='utf-8')
        new = old
        for marker in debrand_cleaner.NAV_MARKERS:
            new = debrand_cleaner.remove_element(new, marker)
        if any(marker in new for marker in debrand_cleaner.NAV_MARKERS):
            raise ValueError('Navigation still present')
        renderer.write_text(new, encoding='utf-8', newline='\n')
        subprocess.run(['node', '--check', str(renderer)], check=True)
        new_asar = temp / 'app.asar'
        subprocess.run(['npx', '--yes', '@electron/asar@3.2.10', 'pack', str(app), str(new_asar)], check=True)
        data = exe.read_bytes()
        before, after = header_sha(asar), header_sha(new_asar)
        if before == after or data.count(before) != 1:
            raise ValueError('Unexpected executable ASAR integrity hash')
        new_exe = temp / 'Sa6i Clean Integration.exe'
        new_exe.write_bytes(data.replace(before, after, 1))
        if sha(new_exe) != OUTPUT_EXE_SHA or sha(new_asar) != OUTPUT_ASAR_SHA:
            raise ValueError('Output hashes do not match the reviewed files')
        # Publish only after checks; no existing file is overwritten.
        output.mkdir()
        shutil.copy2(new_asar, output / 'app.asar')
        shutil.copy2(new_exe, output / new_exe.name)
    print('exe sha256:', sha(output / 'Sa6i Clean Integration.exe'))
    print('asar sha256:', sha(output / 'app.asar'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe')
    parser.add_argument('asar')
    parser.add_argument('output')
    args = parser.parse_args()
    make(args.exe, args.asar, args.output)
