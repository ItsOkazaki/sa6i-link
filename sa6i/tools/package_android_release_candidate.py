#!/usr/bin/env python3
"""Version-locked Android candidate with a supplied reusable signing key.

This patches the distributed APK, not the unrelated source build. It renames
six DEX labels, directs new received files to Download/Sa6i Link, retains the
legacy Android 8/9 FileProvider path, and disables the upstream updater. It does
not migrate existing files. Release only after testing on actual Android phones.
Set SA6I_KEY_PASSWORD in the environment; never commit the keystore or password.
"""
import copy
import importlib.util
import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

spec = importlib.util.spec_from_file_location('branding', Path(__file__).with_name('package_android_branding_candidate.py'))
branding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(branding)


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def replace_method(path, header, body):
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(r'^' + re.escape(header) + r'\n.*?^\.end method$', re.M | re.S)
    modified, count = pattern.subn(lambda _: header + '\n' + body + '\n.end method', text)
    if count != 1:
        raise ValueError(f'Unexpected method {header}: {count}')
    path.write_text(modified, encoding='utf-8')


def patch_resource_table(data):
    """Change only ten global strings; keep all original resource references/IDs.

    Apktool's rebuilt table points to renamed resource files, so it cannot safely
    be combined with the original APK's resource entries. The exact input uses
    a UTF-8 global pool with no styles; fail closed on any different structure.
    """
    data = bytearray(data)
    if struct.unpack_from('<HHI', data, 0) != (2, 12, len(data)):
        raise ValueError('Unexpected resource table header')
    offset = 12
    kind, header, size, count, styles, flags, start, styles_start = struct.unpack_from('<HHIIIIII', data, offset)
    if (kind, header, styles, flags, styles_start) != (1, 28, 0, 0x100, 0) or start != 28 + count * 4:
        raise ValueError('Unexpected global string pool')

    def read_length(pos):
        first = data[pos]
        return (((first & 0x7f) << 8) | data[pos + 1], pos + 2) if first & 0x80 else (first, pos + 1)

    def length(value):
        if value >= 0x8000:
            raise ValueError('String too long')
        return bytes([(value >> 8) | 0x80, value & 0xff]) if value > 0x7f else bytes([value])

    entries, offsets, modified = bytearray(), [], 0
    for i in range(count):
        position = offset + start + struct.unpack_from('<I', data, offset + header + 4 * i)[0]
        utf16_length, cursor = read_length(position)
        byte_length, cursor = read_length(cursor)
        text = bytes(data[cursor:cursor + byte_length]).decode('utf-8')
        if data[cursor + byte_length] != 0 or len(text.encode('utf-16-le')) // 2 != utf16_length:
            raise ValueError('Unexpected global string encoding')
        if 'Download/Nectarlink' in text or 'التنزيل/Nectarlink' in text:
            text = text.replace('Nectarlink', 'Sa6i Link')
            modified += 1
        raw = text.encode('utf-8')
        offsets.append(len(entries))
        entries.extend(length(len(text.encode('utf-16-le')) // 2) + length(len(raw)) + raw + b'\x00')
    if modified != 10:
        raise ValueError('Unexpected number of download guidance strings')
    entries.extend(b'\x00' * (-len(entries) % 4))
    pool_size = start + len(entries)
    pool = struct.pack('<HHIIIIII', kind, header, pool_size, count, styles, flags, start, styles_start)
    pool += b''.join(struct.pack('<I', i) for i in offsets) + entries
    result = data[:offset] + pool + data[offset + size:]
    struct.pack_into('<I', result, 4, len(result))
    return bytes(result)


def patch_decoded(decoded):
    smali = decoded / 'smali'
    for rel, changes in branding.CHANGES.items():
        path = smali / rel
        text = path.read_text(encoding='utf-8')
        for old, new in changes:
            old, new = f'"{old}"', f'"{new}"'
            if text.count(old) != 1:
                raise ValueError(f'Unexpected display string in {rel}: {old}')
            text = text.replace(old, new, 1)
        path.write_text(text, encoding='utf-8')

    # R8 inlined the original `enabled` property. Disable the actual entry
    # points and hide the old controls rather than relying on a source flag.
    updater = smali / 'app/nectarlink/android/update/AppUpdater.smali'
    replace_method(updater, '.method public final latest()Lapp/nectarlink/android/update/AppUpdater$Update;', '    .locals 1\n    const/4 v0, 0x0\n    return-object v0')
    replace_method(updater, '.method public final check(Lkotlin/coroutines/jvm/internal/ContinuationImpl;)Ljava/lang/Object;', '    .locals 1\n    sget-object v0, Ljava/lang/Boolean;->FALSE:Ljava/lang/Boolean;\n    return-object v0')
    for name in ('checkIfDue', 'update', 'updateIfDue', 'installIfAutomatic'):
        replace_method(updater, f'.method public final {name}(Lkotlin/coroutines/jvm/internal/ContinuationImpl;)Ljava/lang/Object;', '    .locals 1\n    sget-object v0, Lkotlin/Unit;->INSTANCE:Lkotlin/Unit;\n    return-object v0')
    ui = smali / 'app/nectarlink/android/update/UpdateCardKt.smali'
    for header in ('.method public static final CheckForUpdates(Lapp/nectarlink/android/update/AppUpdater;Landroidx/compose/runtime/GapComposer;I)V', '.method public static final UpdateCard(Lapp/nectarlink/android/update/AppUpdater;Landroidx/compose/ui/Modifier;Landroidx/compose/runtime/GapComposer;I)V'):
        replace_method(ui, header, '    .locals 0\n    return-void')

    # Only the two specific file-publishing methods get new output paths.
    storage = smali / 'kotlin/jvm/JvmClassMappingKt.smali'
    text = storage.read_text(encoding='utf-8')
    for name in ('toAppDownloads', 'toMediaStore'):
        pattern = re.compile(r'(^\.method public static ' + name + r'\([^\n]*\n.*?^\.end method$)', re.M | re.S)
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            raise ValueError('Unexpected storage method: ' + name)
        method = matches[0].group(1)
        if method.count('"Nectarlink"') != 1:
            raise ValueError('Unexpected storage string in ' + name)
        text = text[:matches[0].start()] + method.replace('"Nectarlink"', '"Sa6i Link"') + text[matches[0].end():]
    storage.write_text(text, encoding='utf-8')

    paths = decoded / 'res/xml/file_paths.xml'
    text = paths.read_text(encoding='utf-8')
    old = '<external-files-path name="received" path="Download/Nectarlink/" />'
    new = '<external-files-path name="received" path="Download/Sa6i Link/" />\n    <external-files-path name="received_legacy" path="Download/Nectarlink/" />'
    if text.count(old) != 1:
        raise ValueError('Unexpected FileProvider paths')
    paths.write_text(text.replace(old, new), encoding='utf-8')

    for locale in ('values', 'values-ar', 'values-de', 'values-tr', 'values-zh-rCN'):
        path = decoded / 'res' / locale / 'strings.xml'
        text = path.read_text(encoding='utf-8')
        for key in ('transfer_received_from', 'guide_files_privacy'):
            pattern = re.compile(r'(<string name="' + key + r'">)(.*?)(</string>)')
            def update(match):
                if match.group(2).count('Nectarlink') != 1:
                    raise ValueError('Unexpected download guidance in ' + str(path))
                return match.group(1) + match.group(2).replace('Nectarlink', 'Sa6i Link') + match.group(3)
            text, count = pattern.subn(update, text)
            if count != 1:
                raise ValueError('Missing download guidance: ' + str(path) + ' ' + key)
        path.write_text(text, encoding='utf-8')


def package(source, output, java, apktool, signer, key):
    source, output, apktool, signer, key = map(Path, (source, output, apktool, signer, key))
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError('Output must be a new, distinct file')
    for path, expected in ((source, branding.INPUT_SHA), (apktool, branding.APKTOOL_SHA), (signer, branding.SIGNER_SHA)):
        if branding.sha(path.read_bytes()) != expected:
            raise ValueError(f'Unexpected file hash: {path}')
    if not os.environ.get('SA6I_KEY_PASSWORD') or not key.is_file():
        raise ValueError('Release keystore and SA6I_KEY_PASSWORD are required')
    output = output.resolve()
    with tempfile.TemporaryDirectory(prefix='sa6i-release-candidate-') as tmp:
        work = Path(tmp)
        decoded, rebuilt, unsigned, signed = (work / x for x in ('decoded', 'rebuilt.apk', 'unsigned.apk', 'signed.apk'))
        run(java, '-Xmx3g', '-jar', apktool, 'd', '-o', decoded, source.resolve())
        patch_decoded(decoded)
        run(java, '-Xmx3g', '-jar', apktool, 'b', '-f', decoded, '-o', rebuilt)
        changed = {'classes.dex', 'resources.arsc', 'res/xml/file_paths.xml'}
        with ZipFile(source) as original, ZipFile(rebuilt) as new:
            if original.testzip() or new.testzip():
                raise ValueError('ZIP integrity failure')
            infos = original.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or not branding.OLD_SIGNATURES.issubset(names) or not changed.issubset(names):
                raise ValueError('Unexpected ZIP layout')
            with ZipFile(unsigned, 'x') as dst:
                dst.comment = original.comment
                for info in infos:
                    if info.filename in branding.OLD_SIGNATURES:
                        continue
                    entry = copy.copy(info)
                    if info.compress_type == ZIP_STORED:
                        align = 16384 if info.filename.startswith('lib/') and info.filename.endswith('.so') else 4
                        base = dst.fp.tell() + 30 + len(info.filename.encode('utf-8')) + len(info.extra)
                        pad = (-(base + 4)) % align
                        entry.extra += struct.pack('<HH', 0xD935, pad) + bytes(pad)
                    if info.filename == 'resources.arsc':
                        payload = patch_resource_table(original.read(info))
                    elif info.filename in changed:
                        payload = new.read(info.filename)
                    else:
                        payload = original.read(info)
                    dst.writestr(entry, payload)
        with ZipFile(source) as original, ZipFile(unsigned) as candidate:
            if candidate.testzip():
                raise ValueError('Candidate ZIP integrity failure')
            for info in candidate.infolist():
                if info.filename not in changed and candidate.read(info) != original.read(info.filename):
                    raise ValueError(f'Unexpected payload modification: {info.filename}')
                if info.compress_type == ZIP_STORED:
                    with unsigned.open('rb') as f:
                        f.seek(info.header_offset + 26)
                        name_size, extra_size = struct.unpack('<HH', f.read(4))
                    offset = info.header_offset + 30 + name_size + extra_size
                    align = 16384 if info.filename.startswith('lib/') and info.filename.endswith('.so') else 4
                    if offset % align:
                        raise ValueError('Misaligned ZIP entry: ' + info.filename)
        run(java, '-jar', signer, 'sign', '--ks', key.resolve(), '--ks-pass', 'env:SA6I_KEY_PASSWORD', '--ks-key-alias', 'sa6i-link-release', '--min-sdk-version', '26', '--out', signed, unsigned)
        run(java, '-jar', signer, 'verify', '--verbose', '--print-certs', '--min-sdk-version', '26', signed)
        with output.open('xb') as target, signed.open('rb') as inp:
            while chunk := inp.read(1024 * 1024):
                target.write(chunk)
    print('Candidate SHA-256:', branding.sha(output.read_bytes()))


if __name__ == '__main__':
    if len(sys.argv) != 7:
        raise SystemExit('Usage: package_android_release_candidate.py INPUT.apk OUTPUT.apk JAVA APKTOOL.jar APKSIGNER.jar KEYSTORE')
    package(*sys.argv[1:])
