#!/usr/bin/env python3
"""Build a separate, experimental Sa6i Clean folder from the exact supplied binaries.

Requires Node.js and @electron/asar 4.3.2 available via npx. This is not a
source build and must not be treated as a tested or release-ready cleaner.
"""
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

RUNTIME_SHA = '2ebb096a9cdfe7ec741bb887f1276c781faa8e4c1c4377a5a44c0ba4e99f9bb6'
EXE_ZIP_SHA = 'ad6a7a588d4895025bc4a3aff251ad781da7e76cf952f8034c1618018a1ee008'
EXE_SHA = '20fd45c3959acac3e6a5a728dc207f8866125f412c76cdcf6c41512b657716b8'
ORIGINAL_HEADER_SHA = 'c5af1334e6c5b35e9d18278a2680be334477becf72fe7ee52107625d27d12613'
ASSETS = Path(__file__).resolve().parent / 'assets'
# Resource offsets for the SHA-256-locked executable only: icon pixels, allocated
# size, resource-directory Size field, icon dimension. No PE sections are moved.
ICON_SLOTS = (
    (248545712, 888, 248486092, 16), (248546600, 1479, 248486108, 24),
    (248548080, 2193, 248486124, 32), (248550280, 3805, 248486140, 48),
    (248554088, 5611, 248486156, 64), (248559704, 13661, 248486172, 128),
    (248573368, 33454, 248486188, 256),
)
ICON_GROUP_OFFSET = 248543472


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def replace_exact(path, before, after, count):
    text = path.read_text(encoding='utf-8')
    if text.count(before) != count:
        raise ValueError(f'Unexpected occurrences in {path.name}: {before!r}')
    path.write_text(text.replace(before, after), encoding='utf-8')


def header_hash(path):
    with path.open('rb') as f:
        prefix = f.read(16)
        _, _, _, size = struct.unpack('<IIII', prefix)
        if not 0 < size < 20_000_000:
            raise ValueError('Invalid ASAR header')
        header = f.read(size)
        if len(header) != size:
            raise ValueError('Truncated ASAR header')
        return hashlib.sha256(header).hexdigest()


def patch_icons(exe):
    """Replace fixed, validated icon resources in the exact inspected executable."""
    with exe.open('r+b') as f:
        f.seek(ICON_GROUP_OFFSET)
        group = bytearray(f.read(104))
        if struct.unpack_from('<HHH', group) != (0, 1, len(ICON_SLOTS)):
            raise ValueError('Unexpected PE icon group')
        changes = []
        for index, (offset, size, size_field, dimension) in enumerate(ICON_SLOTS):
            icon = (ASSETS / f'icon-{dimension}.png').read_bytes()
            if not icon.startswith(b'\x89PNG\r\n\x1a\n') or len(icon) > size:
                raise ValueError(f'Invalid or oversized {dimension}px icon')
            if struct.unpack_from('>II', icon, 16) != (dimension, dimension):
                raise ValueError(f'Wrong dimensions for {dimension}px icon')
            f.seek(offset)
            if f.read(8) != b'\x89PNG\r\n\x1a\n':
                raise ValueError('Unexpected original icon resource')
            f.seek(size_field)
            if struct.unpack('<I', f.read(4))[0] != size:
                raise ValueError('Unexpected PE icon size')
            entry = 6 + index * 14
            width, height, _, _, _, _, original_size, icon_id = struct.unpack_from('<BBBBHHIH', group, entry)
            expected_dimension = dimension % 256
            if (width, height, original_size, icon_id) != (expected_dimension, expected_dimension, size, index + 1):
                raise ValueError('Unexpected icon group entry')
            struct.pack_into('<I', group, entry + 8, len(icon))
            changes.append((offset, size, size_field, icon))
        for offset, size, size_field, icon in changes:
            f.seek(offset)
            f.write(icon + b'\0' * (size - len(icon)))
            f.seek(size_field)
            f.write(struct.pack('<I', len(icon)))
        f.seek(ICON_GROUP_OFFSET)
        f.write(group)


def restrict_test_handlers(main):
    """Block mutating and network IPC entry points in a separate host experiment."""
    disabled = {
        'cleanJunk:r=>SS(r,za)': 'cleanJunk',
        'trashPaths:r=>Zu(r)': 'trashPaths',
        'revealPath:async r=>{$a.showItemInFolder(cC(r))}': 'revealPath',
        'setStartupItem:(r,i)=>Ok(r,i)': 'setStartupItem',
        'uninstallApp:r=>Fk(r)': 'uninstallApp',
        'setSettings:async r=>{let i=await dk(r);return aC(i.theme),i}': 'setSettings',
        'setApiKey:(r,i)=>pk(r,i)': 'setApiKey',
        'askAi:(r,i)=>gk(r,i)': 'askAi',
        'tipsProfile:()=>y_()': 'tipsProfile',
        'startTip:async r=>{let i=await YS(r);return id(i.url)&&await $a.openExternal(i.url),i}': 'startTip',
        'sendFeedback:r=>sS(r,JS())': 'sendFeedback',
        'openExternal:async r=>{id(r)&&await $a.openExternal(r)}': 'openExternal',
    }
    for original, name in disabled.items():
        replace_exact(main, original,
                      name + ':async()=>{throw new Error("Disabled in the Sa6i integration experiment")}', 1)


def build(runtime, exe_zip, output, restricted=False):
    if sha(runtime) != RUNTIME_SHA or sha(exe_zip) != EXE_ZIP_SHA:
        raise ValueError('Inputs do not match the inspected Cleanly 0.2.0 files')
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sa6i-clean-', dir=output.parent) as tmp:
        work = Path(tmp)
        folder = work / 'Sa6i Clean'
        folder.mkdir()
        with ZipFile(runtime) as z:
            for info in z.infolist():
                path = PurePosixPath(info.filename)
                if not path.parts or path.parts[0] != 'clean' or '..' in path.parts or path.is_absolute():
                    raise ValueError(f'Unsafe archive path: {info.filename}')
                relative = path.parts[1:]
                if not relative or info.is_dir() or relative == ('Uninstall Cleanly.exe',):
                    continue
                dest = folder.joinpath(*relative)
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as source, dest.open('wb') as target:
                    shutil.copyfileobj(source, target)
        exe = folder / 'Sa6i Clean.exe'
        with ZipFile(exe_zip) as z:
            if z.namelist() != ['Cleanly.exe']:
                raise ValueError('Unexpected executable archive contents')
            with z.open('Cleanly.exe') as source, exe.open('wb') as target:
                shutil.copyfileobj(source, target)
        if sha(exe) != EXE_SHA:
            raise ValueError('Executable checksum mismatch')
        asar = folder / 'resources' / 'app.asar'
        if header_hash(asar) != ORIGINAL_HEADER_SHA:
            raise ValueError('Executable and ASAR do not match')
        app = work / 'app'
        subprocess.run(['npx', '--yes', '@electron/asar@4.3.2', 'extract', str(asar), str(app)], check=True)
        package = app / 'package.json'
        data = json.loads(package.read_text(encoding='utf-8'))
        if data['name'] != 'cleanly' or data['productName'] != 'Cleanly' or data['version'] != '0.2.0':
            raise ValueError('Unexpected app metadata')
        data['name'] = 'sa6i-clean-host-test' if restricted else 'sa6i-clean'
        data['productName'] = 'Sa6i Clean Host Test' if restricted else 'Sa6i Clean'
        package.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        replace_exact(app / 'dist/index.html', '<title>Cleanly</title>', '<title>Sa6i Clean</title>', 1)
        main = app / 'dist-electron/main.js'
        replace_exact(main, 'title:"Cleanly",titleBarStyle', 'title:"Sa6i Clean",titleBarStyle', 1)
        if restricted:
            restrict_test_handlers(main)
        ui = app / 'dist/assets/index-BwXp8TnN.js'
        replace_exact(ui, 'children:`cleanly`', 'children:`Sa6i Clean`', 2)
        replace_exact(ui, 'sub:`Make Cleanly feel like yours.', 'sub:`Make Sa6i Clean feel like yours.', 1)
        replace_exact(ui, 'children:`Cleanly does not replace your antivirus.', 'children:`Sa6i Clean does not replace your antivirus.', 1)
        replace_exact(ui, 'sub:`Caches, temp files and logs your apps rebuild on their own. Safe items are picked for you.`',
                      'sub:`Warning: cleanup can permanently delete selected files, including Recycle Bin contents. Review selections and back up first.`', 1)
        replace_exact(ui, 'Caches and temp files are deleted for good — they rebuild themselves. Your own files always go to Trash.',
                      'Cleanup can permanently delete files. Review selections and back up anything important first.', 1)
        replace_exact(ui, 'title:`Send feedback`', 'title:`Send feedback to the original Cleanly developer`', 1)
        old_logo = 'function Ee({size:e=30}){return(0,F.jsxs)(`svg`,{className:`brand-mark`,width:e,height:e,viewBox:`0 0 32 32`,"aria-hidden":`true`,children:[(0,F.jsx)(`path`,{d:`M16 2c1.2 7.4 6.6 12.8 14 14-7.4 1.2-12.8 6.6-14 14-1.2-7.4-6.6-12.8-14-14C9.4 14.8 14.8 9.4 16 2z`,fill:`url(#g-brand)`}),(0,F.jsx)(`circle`,{cx:`25`,cy:`7`,r:`2.4`,fill:`#ffb547`})]})}'
        new_logo = 'function Ee({size:e=30}){return(0,F.jsx)(`img`,{className:`brand-mark`,width:e,height:e,src:`./assets/sa6i-clean.png`,alt:``})}'
        replace_exact(ui, old_logo, new_logo, 1)
        shutil.copyfile(ASSETS / 'icon-128.png', app / 'dist/assets/sa6i-clean.png')
        # Keep the upstream developer's tip and feedback branding and endpoints intact.
        replace_exact(ui, 'title:`Support Cleanly`', 'title:`Support Cleanly (original developer)`', 2)
        asar.unlink()
        subprocess.run(['npx', '--yes', '@electron/asar@4.3.2', 'pack', str(app), str(asar)], check=True)
        updated_hash = header_hash(asar)
        old = ORIGINAL_HEADER_SHA.encode('ascii')
        new = updated_hash.encode('ascii')
        # The original unsigned executable has one integrity resource containing this hash.
        with exe.open('r+b') as f:
            content = f.read()
            if content.count(old) != 1:
                raise ValueError('Executable integrity hash is not unique')
            offset = content.index(old)
            del content
            f.seek(offset)
            f.write(new)
        patch_icons(exe)
        (folder / 'SA6I-CLEAN-TEST-NOTICE.txt').write_text(
            'EXPERIMENTAL TEST ONLY - NOT A RELEASE\n'
            'Based on Cleanly 0.2.0 by 0xCodez; modified with permission supplied by the user.\n'
            'This is an unsigned, patched packaged application, not a source build.\n'
            'The user reports an earlier candidate works on Windows 7 with VxKex; full compatibility is unverified.\n'
            'Do not run cleanup, uninstall apps, or change startup items on a production PC.\n'
            'Some cleanup deletes files permanently rather than using the Recycle Bin.\n'
            'Support and feedback features retain the original Cleanly services.\n'
            'Windows file metadata and some messages still identify Cleanly.\n'
            'Install in a separate folder; never overwrite the original application.\n'
            + ('Host test: selected destructive, settings, and network IPC operations are disabled. '
               'This is not a security audit; do not test against valuable files.\n' if restricted else ''), encoding='utf-8')
        shutil.copyfile(Path(__file__).resolve().parent / 'SAFETY-REVIEW.md', folder / 'SAFETY-REVIEW.md')
        shutil.move(str(folder), str(output))
    print('Created', output)
    print('Updated ASAR header SHA-256:', updated_hash)
    print('Executable SHA-256:', sha(output / 'Sa6i Clean.exe'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime_zip', type=Path)
    parser.add_argument('exe_zip', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--restricted', action='store_true', help='block mutating and network IPC for a host experiment')
    args = parser.parse_args()
    build(args.runtime_zip.resolve(), args.exe_zip.resolve(), args.output.resolve(), args.restricted)
