#!/usr/bin/env python3
"""Assemble the hardened Sa6i Link candidate from the tested one.

Two files change: the cleaner's ASAR/executable (cache-root guard, produced by
`harden_cleaner.py`) and the desktop executable's two compiled-in expected
digests. Every other byte, entry order, timestamp and attribute is preserved
from the tested archive. No binary is executed.

The desktop verifies the cleaner's exact SHA-256 before launching it, so its
allowlist constants are replaced in place rather than rebuilt; the replacement
is counted and the result is checked to differ only in those 64 bytes.
"""
import argparse
import copy
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

INPUT_SHA = '9eff3b026f4c1392222282214b126281ef60e1731b5a26bbdc8bf0138649c935'
OLD_EXE_SHA = 'e991d57efbb8de204a7fb9e9f5b3ef5fe34531e37e77556f66f079545a866a3f'
OLD_ASAR_SHA = 'b3af2dd8355194905fc929ccd1d40dcaa78542208cc4b0d0612c50bf9d93e83f'
NEW_EXE_SHA = '2c9bdd29209ebc58103753a2a66d8b9c840d94054eea368239566b5d42408d74'
NEW_ASAR_SHA = '4cbe981c5a473d61a7b679e61db49b4c5a0a052ba5783ce903054b46562a10ba'
OLD_ROOT = 'Sa6i Link Integrated Candidate/'
NEW_ROOT = 'Sa6i Link Hardened Candidate/'
DESKTOP = 'sa6i-link.exe'
CLEAN_EXE = 'Sa6i Clean/Sa6i Clean Integration.exe'
CLEAN_ASAR = 'Sa6i Clean/resources/app.asar'

README = '''SA6I LINK HARDENED CANDIDATE - TEST BUILD, NOT A FINAL RELEASE

This is the tested Sa6i Link candidate with one change: Sa6i Clean now refuses
to clean a cache folder whose own path, or any folder above it, is a junction
or symlink. That closes the redirected-folder gap found in the review. The
guard was exercised on a disposable Windows runner against synthetic files
only. The app itself has NOT been run with the guard on a real machine, and no
cleanup, Recycle Bin, uninstall or startup action has been validated anywhere.

The cleaner's files differ from the previous candidate, so this build has not
been launched yet. Expect to test it before trusting it. Windows 7 may need
VxKex enabled separately for sa6i-link.exe and Sa6i Clean\\Sa6i Clean
Integration.exe. Existing pairings and settings do not automatically transfer;
this launcher uses its own app data directory. A separate profile is NOT a
sandbox, and the cleaner can still delete files permanently.

Extract to a NEW folder, never over an existing installation or preview. Run
Start Sa6i Link Candidate.cmd. Keep the previous candidate as the fallback.
This unsigned build is not identical to the original released Sa6i Link. The
Win7 cldapi compatibility shim disables Explorer phone-storage integration.

See LICENSES, THIRD-PARTY-NOTICES.txt, QT-BACKPORT-SOURCES.txt, SA6I-NOTICE.md,
SA6I-HARDENING.md and the notices in the Sa6i Clean folder.
'''

HARDENING_NOTES = '''SA6I CLEAN CACHE-ROOT GUARD (HARDENING NOTE)

What changed: the cleaner deletes cache contents with fs.unlink/fs.rmdir. Its
upstream code validated the file being deleted, but not the folder the file
lives in, so a junction or symlink above a cache root could route deletion into
whatever that redirect pointed at. The guarded build walks every component of
the cache root and refuses that category when any component is a link. The
refusal is safe: the category is skipped and counted as blocked for safety.

Evidence: source patch and packaged patch are the same logic
(sa6i/clean/harden_upstream.py, sa6i/clean/harden_cleaner.py,
sa6i/clean/guard_snippet.js). The guard accepted ordinary folders, refused a
junction above a cache root, and left data untouched on a disposable Windows
runner (workflow "Sa6i Clean Windows cleanup probe"), which also confirmed that
8.3 short-name spellings do not cause false refusals.

Not evidence of safety: no cleanup has been run in the real application. The
cleaner is unsigned and based on Cleanly 0.2.0 by 0xCodez, modified with
permission supplied by the user.
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entry_name(name):
    """Rename only the archive's top-level folder."""
    return NEW_ROOT + name[len(OLD_ROOT):] if name.startswith(OLD_ROOT) else name


def patch_desktop(data):
    old_exe, new_exe = bytes.fromhex(OLD_EXE_SHA), bytes.fromhex(NEW_EXE_SHA)
    old_asar, new_asar = bytes.fromhex(OLD_ASAR_SHA), bytes.fromhex(NEW_ASAR_SHA)
    for old in (old_exe, old_asar):
        if data.count(old) != 1:
            raise ValueError('Expected exactly one compiled-in cleaner digest in the desktop executable')
    patched = data.replace(old_exe, new_exe, 1).replace(old_asar, new_asar, 1)
    if len(patched) != len(data) or patched.count(new_exe) != 1 or patched.count(new_asar) != 1:
        raise ValueError('Desktop digest replacement failed its own check')
    differing = sum(1 for a, b in zip(data, patched) if a != b)
    if differing != 64:
        raise ValueError(f'Desktop executable changed in {differing} bytes, expected 64')
    return patched


def build(candidate, clean_exe, clean_asar, output):
    candidate, clean_exe, clean_asar, output = (
        Path(candidate).absolute(), Path(clean_exe).absolute(), Path(clean_asar).absolute(), Path(output).absolute())
    if sha(candidate) != INPUT_SHA:
        raise ValueError('Input archive is not the tested candidate')
    if sha(clean_exe) != NEW_EXE_SHA or sha(clean_asar) != NEW_ASAR_SHA:
        raise ValueError('Hardened cleaner files do not match their pinned hashes')
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Refusing to overwrite {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    docs = Path(__file__).resolve().parent
    replacements = {}
    with tempfile.TemporaryDirectory(prefix='.sa6i-hardened-', dir=output.parent) as tmp:
        staged = Path(tmp) / 'candidate.zip'
        with ZipFile(candidate) as src:
            infos = src.infolist()
            if not infos or not all(i.filename.startswith(OLD_ROOT) for i in infos):
                raise ValueError('Unexpected archive layout')
            template = src.getinfo(OLD_ROOT + 'READ FIRST - CANDIDATE.txt')
            payloads = []
            for info in infos:
                old_name = info.filename
                data = b'' if info.is_dir() else src.read(old_name)
                relative = old_name[len(OLD_ROOT):] if old_name.startswith(OLD_ROOT) else None
                if relative == DESKTOP:
                    data = patch_desktop(data)
                    replacements[relative] = hashlib.sha256(data).hexdigest()
                elif relative == CLEAN_EXE:
                    data = clean_exe.read_bytes()
                    replacements[relative] = hashlib.sha256(data).hexdigest()
                elif relative == CLEAN_ASAR:
                    data = clean_asar.read_bytes()
                    replacements[relative] = hashlib.sha256(data).hexdigest()
                elif relative == 'READ FIRST - CANDIDATE.txt':
                    data = README.replace('\n', '\r\n').encode('utf-8')
                elif relative == 'Sa6i Clean/SAFETY-REVIEW.md':
                    data = (docs / 'SAFETY-REVIEW.md').read_bytes()
                elif relative == 'Sa6i Clean/RELEASE-READINESS.md':
                    data = (docs / 'RELEASE-READINESS.md').read_bytes()
                elif relative == 'Sa6i Clean/SA6I-CLEAN-TEST-NOTICE.txt':
                    data = HARDENING_NOTES.replace('\n', '\r\n').encode('utf-8')
                new_info = copy.copy(info)
                new_info.filename = entry_name(old_name)
                payloads.append((new_info, data))
            hardening = copy.copy(template)
            hardening.filename = NEW_ROOT + 'SA6I-HARDENING.md'
            payloads.append((hardening, HARDENING_NOTES.replace('\n', '\r\n').encode('utf-8')))
        with ZipFile(staged, 'w', ZIP_DEFLATED, allowZip64=False) as dst:
            for info, data in payloads:
                dst.writestr(info, data)
        os.replace(staged, output)
    return output, replacements


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('candidate', type=Path, help='tested candidate ZIP')
    parser.add_argument('clean_exe', type=Path, help='hardened Sa6i Clean executable')
    parser.add_argument('clean_asar', type=Path, help='hardened app.asar')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    out, replacements = build(args.candidate, args.clean_exe, args.clean_asar, args.output)
    with ZipFile(out) as z:
        print('Archive:', out)
        print('Entries:', len(z.namelist()), 'ZIP64:', any(i.header_offset == 0xffffffff for i in z.infolist()))
    for name, digest in replacements.items():
        print(f'{name}: {digest}')
    print('Archive SHA-256:', sha(out))
    print('Untested build: no cleanup has been run with this guard in the app.')


if __name__ == '__main__':
    main()
