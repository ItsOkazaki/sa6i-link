#!/usr/bin/env python3
"""Assemble a separate experimental ZIP from the known preview and speed update.

This is NOT a final release, installer, sandbox, or cleanup-safety validation.
Both input archives are hash-locked; no binaries are executed or modified.
"""
import argparse
import secrets
import shutil
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from verify_clearance_preview import archive_files, sha_stream

BASE_SHA = '068430f9c5ba9376a474134ba13db19817a93a0196a7f692101df40640459d50'
SPEED_SHA = '52418de708afda8f66bd629179f34b9809dfa93edb72babab83bc7b90ca436bb'
BASE_ROOT = 'Sa6i Link Unified Preview/'
OUT_ROOT = 'Sa6i Link Integrated Candidate/'
DESKTOP_SHA = '721d78f06554ca26c825de46f89ea1fc7294426d1a581e8312d2a49d635ef92f'
VCAM_SHA = '9a6a57cf13a2dc3e8787daaad2c1660a7149353a68a3d1dbafa28349a38307ca'
CLEAN_EXE_SHA = 'e991d57efbb8de204a7fb9e9f5b3ef5fe34531e37e77556f66f079545a866a3f'
CLEAN_ASAR_SHA = 'b3af2dd8355194905fc929ccd1d40dcaa78542208cc4b0d0612c50bf9d93e83f'
SHIM_SHA = 'e4bb7c947223b56284ff05548434a0bb178faa147ce5157a94c771e3b11b276b'
# Old launchers would select obsolete flags or profiles; do not ship them.
REPLACED = {'nectarlink-desktop.exe', 'nectarlink_vcam.dll',
            'Start Integrated Test.cmd', 'Start Win7 Compatibility Test.cmd',
            'READ FIRST - EXPERIMENT.txt', 'INTEGRATION-BUILD-ONLY.txt'}
README = '''SA6I LINK INTEGRATED CANDIDATE - EXPERIMENTAL, NOT A FINAL RELEASE

This folder contains Sa6i Link with Sa6i Clean in the same window, including
the header-clearance and reopen-speed changes. The user reported that this
assembled package works on one Windows 7/VxKex setup, after reporting that the
earlier preview looked good and reopened faster. That report covers launching
and using the interface only; no cleanup or system-management action has been
exercised, and Windows 10/11 behaviour is unverified.

Extract to a NEW folder, never over an existing installation or preview. Run
Start Sa6i Link Candidate.cmd. Windows 7 may need VxKex enabled separately
for nectarlink-desktop.exe and Sa6i Clean\\Sa6i Clean Integration.exe.
Existing pairings and settings do not automatically transfer; this launcher
uses its own test app data directory. A separate profile is NOT a sandbox.

The full cleaner can permanently delete files, empty the Recycle Bin, change
startup entries and launch uninstallers. Cleanup and system management have
NOT been safety-validated. Use only a disposable environment with verified
backups; do not use it for real cleanup or on important files. This unsigned
source build is not identical to the original released Sa6i Link. The Win7
cldapi compatibility shim disables Explorer phone-storage integration; app
update and other system integration features are disabled in this experiment.

The original app and previous preview remain the fallback. See LICENSES,
THIRD-PARTY-NOTICES.txt, QT-BACKPORT-SOURCES.txt, SA6I-NOTICE.md and the
notices in the Sa6i Clean folder. Compatibility, security, feature behavior
and licensing requirements still need review before a production release.
'''


def check_zip(path, expected):
    with path.open('rb') as stream:
        if sha_stream(stream) != expected:
            raise ValueError('Unrecognized input archive: ' + str(path))


def require_digest(index, path, digest):
    entry = index.get(path.casefold())
    if entry is None or entry[2] != digest:
        raise ValueError('Missing or mismatched package component: ' + path)


def build(base, speed, output):
    base, speed, output = (Path(p).absolute() for p in (base, speed, output))
    check_zip(base, BASE_SHA)
    check_zip(speed, SPEED_SHA)
    if output.exists() or output.is_symlink():
        raise FileExistsError('Refusing to overwrite ' + str(output))
    # All sources are exact pinned archives; no extracted input is changed.
    with ZipFile(base) as bz, ZipFile(speed) as sz:
        base_index, speed_index = archive_files(bz, BASE_ROOT), archive_files(sz, '')
        for path, digest in ((r'Sa6i Clean/Sa6i Clean Integration.exe', CLEAN_EXE_SHA),
                             ('Sa6i Clean/resources/app.asar', CLEAN_ASAR_SHA),
                             ('cldapi.dll', SHIM_SHA)):
            require_digest(base_index, path, digest)
        require_digest(speed_index, 'nectarlink-desktop.exe', DESKTOP_SHA)
        require_digest(speed_index, 'nectarlink_vcam.dll', VCAM_SHA)
        if not all(name.casefold() in base_index for name in REPLACED):
            raise ValueError('Base archive is missing an expected replaced file')
        launcher = sz.read('Start Reopen Speed Test.cmd')
        # Preserve every tested option but use a fresh app data directory so
        # this package cannot accidentally share the previous preview profile.
        lines = launcher.splitlines(keepends=True)
        candidates = [i for i, line in enumerate(lines) if line.startswith(b'set "SA6I_DATA=')]
        if len(candidates) != 1 or b'--sa6i-clean-header-clearance' not in launcher:
            raise ValueError('Unexpected speed-test launcher')
        lines[candidates[0]] = (b'set "SA6I_DATA=%LOCALAPPDATA%\\Sa6i-Link-Candidate-' +
                                secrets.token_hex(12).encode('ascii') + b'"\r\n')
        launcher = b''.join(lines)
        expected = {key: v for key, v in base_index.items() if v[0] not in REPLACED}
        for name in ('nectarlink-desktop.exe', 'nectarlink_vcam.dll'):
            expected[name.casefold()] = speed_index[name.casefold()]
        output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation refuses replacement even if another process races.
        created = False
        try:
            raw = output.open('xb')
            created = True
            # This pinned package is well below classic ZIP limits. Avoid
            # ZIP64 for Windows 7 compatibility; actual extraction is untested.
            with raw, ZipFile(raw, 'w', compression=ZIP_DEFLATED, compresslevel=6, allowZip64=False) as out:
                for info in bz.infolist():
                    relative = info.filename[len(BASE_ROOT):]
                    if info.is_dir():
                        if relative:
                            out.writestr(OUT_ROOT + relative, b'')
                        continue
                    if relative in REPLACED:
                        continue
                    with bz.open(info) as src, out.open(OUT_ROOT + relative, 'w') as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
                for name in ('nectarlink-desktop.exe', 'nectarlink_vcam.dll'):
                    with sz.open(name) as src, out.open(OUT_ROOT + name, 'w') as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
                out.writestr(OUT_ROOT + 'Start Sa6i Link Candidate.cmd', launcher)
                out.writestr(OUT_ROOT + 'READ FIRST - CANDIDATE.txt', README.replace('\n', '\r\n').encode('utf-8'))
                out.writestr(OUT_ROOT + 'INTEGRATION-BUILD-ONLY.txt',
                             b'Experimental integration candidate. Read READ FIRST - CANDIDATE.txt.\r\n')
            with ZipFile(output) as result:
                actual = archive_files(result, OUT_ROOT)
                for key, (_, size, digest) in expected.items():
                    if key not in actual or actual[key][1:] != (size, digest):
                        raise ValueError('Output verification failed: ' + key)
                extras = {'start sa6i link candidate.cmd', 'read first - candidate.txt', 'integration-build-only.txt'}
                if set(actual) != set(expected) | extras:
                    raise ValueError('Unexpected output archive inventory')
                if result.read(OUT_ROOT + 'Start Sa6i Link Candidate.cmd') != launcher:
                    raise ValueError('Launcher verification failed')
        except BaseException:
            # Only remove a file we exclusively created; never delete inputs.
            if created:
                output.unlink(missing_ok=True)
            raise
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_zip', type=Path)
    parser.add_argument('speed_update_zip', type=Path)
    parser.add_argument('output_zip', type=Path)
    args = parser.parse_args()
    path = build(args.base_zip, args.speed_update_zip, args.output_zip)
    with path.open('rb') as stream:
        print('Created experimental candidate:', path, 'SHA256:', sha_stream(stream))


if __name__ == '__main__':
    main()
