#!/usr/bin/env python3
"""Build a *test-only*, differently signed APK from the exact supplied APK.

Only six display/device-name string constants in classes.dex are changed. All
other non-signature entries, including the original resources and manifest, are
copied unchanged. The temporary signing key is destroyed when this script ends:
this candidate is not a release, cannot update the original installation, and
cannot be updated again using this key. Never remove an installed app without
backing up its data and understanding the risk.

Requires Java 17, keytool, Apktool 2.9.3 (official SHA-256 below) and Android
apksigner 0.9 (SHA-256 below, mirrored from Android SDK build tools 34.0.0).
"""
import copy
import hashlib
import os
import secrets
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

INPUT_SHA = '86913c1ab9ac5f1aac060b966708a0fc4442fd56e02df7cbc2dc4a4a1d92b5b1'
APKTOOL_SHA = '7956eb04194300ce0d0a84ad18771eebc94b89fb8d1ddcce8ea4c056818646f4'
SIGNER_SHA = 'eefdd6aed9db9fb849e4c98a50d8741e19d1b674ba6547220bcb9c3ed152123a'
CHANGES = {
    'androidx/activity/EdgeToEdge$$ExternalSyntheticLambda0.smali': [('Sa6i Link PC media', 'Sa6i Link PC media')],
    'app/sa6i-link/android/elevated/InputServer$Injector.smali': [('Sa6i Link Virtual Keyboard', 'Sa6i Link Virtual Keyboard'), ('Sa6i Link Virtual Gamepad', 'Sa6i Link Virtual Gamepad')],
    'app/sa6i-link/android/core/Core.smali': [('Phone speaker (Sa6i Link)', 'Phone speaker (Sa6i Link)')],
    'app/sa6i-link/android/core/Core$onTransfer$2.smali': [('Sa6i Link file', 'Sa6i Link file')],
    'app/sa6i-link/android/core/Core$joinWithLink$1.smali': [('not a Sa6i Link code', 'not a Sa6i Link code')],
}
OLD_SIGNATURES = {'META-INF/SA6ITEST.SF', 'META-INF/SA6ITEST.RSA', 'META-INF/MANIFEST.MF'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def package(source, output, java, keytool, apktool, signer):
    source, output, apktool, signer = map(Path, (source, output, apktool, signer))
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError('Output must be a new, distinct file')
    for path, expected in ((source, INPUT_SHA), (apktool, APKTOOL_SHA), (signer, SIGNER_SHA)):
        if sha(path.read_bytes()) != expected:
            raise ValueError(f'Unexpected file hash: {path}')
    output = output.resolve()
    with tempfile.TemporaryDirectory(prefix='sa6i-android-test-') as work:
        work = Path(work)
        decoded, rebuilt, unsigned, key = (work / x for x in ('decoded', 'rebuilt.apk', 'unsigned.apk', 'test.jks'))
        run(java, '-Xmx3g', '-jar', apktool, 'd', '-o', decoded, source.resolve())
        for rel, pairs in CHANGES.items():
            p = decoded / 'smali' / rel
            text = p.read_text(encoding='utf-8')
            for old, new in pairs:
                old, new = f'"{old}"', f'"{new}"'
                if text.count(old) != 1:
                    raise ValueError(f'Unexpected smali occurrence in {rel}: {old}')
                text = text.replace(old, new, 1)
            p.write_text(text, encoding='utf-8')
        run(java, '-Xmx3g', '-jar', apktool, 'b', '-f', decoded, '-o', rebuilt)
        with ZipFile(source) as original, ZipFile(rebuilt) as rebuilt_zip:
            if original.testzip() or rebuilt_zip.testzip():
                raise ValueError('ZIP integrity failure')
            infos = original.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or not OLD_SIGNATURES.issubset(names) or names.count('classes.dex') != 1:
                raise ValueError('Unexpected ZIP entries')
            dex = rebuilt_zip.read('classes.dex')
            with ZipFile(unsigned, 'x') as dst:
                dst.comment = original.comment
                for info in infos:
                    if info.filename in OLD_SIGNATURES:
                        continue
                    new_info = copy.copy(info)
                    if info.compress_type == ZIP_STORED:
                        align = 16384 if info.filename.startswith('lib/') and info.filename.endswith('.so') else 4
                        base = dst.fp.tell() + 30 + len(info.filename.encode('utf-8')) + len(info.extra)
                        pad = (-(base + 4)) % align
                        new_info.extra += struct.pack('<HH', 0xD935, pad) + bytes(pad)
                    data = dex if info.filename == 'classes.dex' else original.read(info)
                    dst.writestr(new_info, data)
        # Verify every unchanged payload and uncompressed native library alignment.
        with ZipFile(source) as original, ZipFile(unsigned) as candidate:
            if candidate.testzip():
                raise ValueError('Candidate ZIP integrity failure')
            for info in candidate.infolist():
                if info.filename != 'classes.dex' and candidate.read(info) != original.read(info.filename):
                    raise ValueError(f'Unexpected modification: {info.filename}')
                if info.compress_type == ZIP_STORED:
                    with unsigned.open('rb') as f:
                        f.seek(info.header_offset + 26)
                        fnlen, extralen = struct.unpack('<HH', f.read(4))
                    offset = info.header_offset + 30 + fnlen + extralen
                    align = 16384 if info.filename.startswith('lib/') and info.filename.endswith('.so') else 4
                    if offset % align:
                        raise ValueError(f'Misaligned ZIP entry: {info.filename}')
        password = secrets.token_urlsafe(24)
        run(keytool, '-genkeypair', '-keystore', key, '-storetype', 'PKCS12', '-storepass', password,
            '-keypass', password, '-alias', 'sa6i-temporary-test', '-keyalg', 'RSA', '-keysize', '2048',
            '-validity', '3650', '-dname', 'CN=Sa6i Link temporary test', '-noprompt')
        # -x above ensures an existing output is never overwritten. Sign in the
        # temporary directory first and publish only after successful verification.
        signed = work / 'signed.apk'
        run(java, '-jar', signer, 'sign', '--ks', key, '--ks-pass', 'pass:' + password,
            '--ks-key-alias', 'sa6i-temporary-test', '--min-sdk-version', '26', '--out', signed, unsigned)
        run(java, '-jar', signer, 'verify', '--verbose', '--min-sdk-version', '26', signed)
        with output.open('xb') as target, signed.open('rb') as inp:
            while chunk := inp.read(1024 * 1024):
                target.write(chunk)
    print('Candidate SHA-256:', sha(output.read_bytes()))
    print('Temporary test signing key discarded; NOT an update or release build.')


if __name__ == '__main__':
    if len(sys.argv) != 7:
        raise SystemExit('Usage: package_android_branding_candidate.py INPUT.apk OUTPUT.apk JAVA KEYTOOL APKTOOL.jar APKSIGNER.jar')
    package(*sys.argv[1:])
