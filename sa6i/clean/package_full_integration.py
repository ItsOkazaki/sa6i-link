#!/usr/bin/env python3
"""Assemble a separate full-cleaner integration candidate, never an installer.

Requires an already staged Windows build compiled with BOTH experimental flags
and the exact themed cleaner prepared by prepare_themed_fixture.py from the
full fixture. This does not validate Windows compatibility, OS isolation, or
cleanup safety.
"""
import argparse
from pathlib import Path
import secrets
import shutil
import tempfile

from prepare_full_integration import OUTPUT_NAME, sha
from prepare_themed_fixture import THEMED_ASAR_SHA as ASAR_SHA, THEMED_EXE_SHA as OUTPUT_SHA

# Exact app-local compatibility shim from the user's original Sa6i Link ZIP.
# It disables Windows Explorer phone-storage integration on systems lacking
# the Windows Cloud Files API; it is not a full cldapi implementation.
WIN7_SHIM_SHA = 'e4bb7c947223b56284ff05548434a0bb178faa147ce5157a94c771e3b11b276b'


def reject_links(root):
    if root.is_symlink():
        raise ValueError(f'Symbolic link not allowed: {root}')
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError(f'Symbolic link not allowed: {path}')


def package(desktop, cleaner, output, win7_shim):
    desktop, cleaner, output, win7_shim = (p.absolute() for p in (desktop, cleaner, output, win7_shim))
    if win7_shim.is_symlink() or not win7_shim.is_file() or sha(win7_shim) != WIN7_SHIM_SHA:
        raise ValueError('Windows 7 compatibility shim does not match the supplied original')
    if not desktop.is_dir() or not cleaner.is_dir():
        raise ValueError('Desktop and cleaner must be existing directories')
    # Never make an output within an input or replace any existing output.
    for source in (desktop, cleaner):
        if output == source or source in output.parents or output in source.parents:
            raise ValueError('Inputs and output must be separate directories')
        reject_links(source)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Refusing to overwrite {output}')
    binary = desktop / 'nectarlink-desktop.exe'
    if not binary.is_file() or not (desktop / 'Qt6Core.dll').is_file():
        raise ValueError('Not a staged Windows desktop build')
    # The filename and both immutable SHA-256 constants are linked into the
    # native backend only in the opt-in full-fixture configuration.
    exe_data = binary.read_bytes()
    if (OUTPUT_NAME.encode('utf-16le') not in exe_data or
            bytes.fromhex(OUTPUT_SHA) not in exe_data or
            bytes.fromhex(ASAR_SHA) not in exe_data):
        raise ValueError('Desktop build does not contain the pinned full-cleaner fixture')
    if sha(cleaner / OUTPUT_NAME) != OUTPUT_SHA or sha(cleaner / 'resources' / 'app.asar') != ASAR_SHA:
        raise ValueError('Cleaner fixture does not match the desktop build')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.sa6i-integrated-', dir=output.parent) as work:
        staged = Path(work) / 'Sa6i Link Integrated'
        shutil.copytree(desktop, staged)
        # Never replace an unexpected DLL silently. The known app-local shim is
        # required for the user's Windows 7 machine and stays beside the app.
        staged_shim = staged / 'cldapi.dll'
        if staged_shim.exists() and (not staged_shim.is_file() or sha(staged_shim) != WIN7_SHIM_SHA):
            raise ValueError('Desktop contains an unexpected cldapi.dll')
        if not staged_shim.exists():
            shutil.copyfile(win7_shim, staged_shim)
        if sha(staged_shim) != WIN7_SHIM_SHA:
            raise ValueError('Copied compatibility shim checksum mismatch')
        # The prepared copy is identical to Sa6i Clean.exe apart from its PE
        # header; avoid shipping two 243 MB executables.
        shutil.copytree(cleaner, staged / 'Sa6i Clean',
                        ignore=lambda path, names: {'Sa6i Clean.exe'} if Path(path) == cleaner else set())
        # The original build-only note says the cleaner is absent, which is no
        # longer true after assembly; replace it only in this staging folder.
        (staged / 'INTEGRATION-BUILD-ONLY.txt').write_text(
            'Experimental integration build; the full cleaner is now included. '
            'Read READ FIRST - EXPERIMENT.txt before use.\n', encoding='utf-8')
        source_root = Path(__file__).resolve().parents[2]
        shutil.copytree(source_root / 'LICENSES', staged / 'LICENSES')
        shutil.copyfile(source_root / 'sa6i' / 'NOTICE.md', staged / 'SA6I-NOTICE.md')
        (staged / 'QT-BACKPORT-SOURCES.txt').write_text(
            'This candidate uses the separately distributed third-party Qt 6.8.3 '
            'Windows 7 backport from xanasoft, based on crystalidea/qt6windows7.\n'
            'Build archive SHA-256: f1efe461b28d7758e1e68ba189d0a45c8168ac181be1ffe7013d0bbfb6ff145d\n'
            'Build and corresponding source archive: https://github.com/xanasoft/qt-builds/releases/tag/v6.8.3-ssl-lgpl\n'
            'Source archive SHA-256: 3e8499a9e977f06c74f57a1a98af67c528013e5973a47dbb5ee0c02f6fe1063d\n'
            'Backport project: https://github.com/crystalidea/qt6windows7\n'
            'Qt license text and additional notices are in THIRD-PARTY-NOTICES.txt. '
            'This notice does not replace a review of distribution obligations.\n',
            encoding='utf-8')
        unique = secrets.token_hex(12)
        launch = f'''@echo off\r
setlocal\r
if not defined LOCALAPPDATA (echo LOCALAPPDATA is unavailable. & pause & exit /b 1)\r
set "SA6I_CLEAN_WIN7_COMPAT=1"\r
set "SA6I_CLEAN_WIN7_SOFTWARE=1"\r
set "QT_QUICK_BACKEND=software"\r
set "SA6I_DATA=%LOCALAPPDATA%\\Sa6i-Link-Integrated-Test-{unique}"\r
start "" "%~dp0nectarlink-desktop.exe" --data-dir "%SA6I_DATA%" "--sa6i-clean-test-dir=%~dp0Sa6i Clean"\r
'''
        (staged / 'Start Integrated Test.cmd').write_bytes(launch.encode('ascii'))
        # Allow a comparison with the earlier rendering path when the software
        # compositor produces a blank viewport. Explicitly clear inherited
        # overrides; these launchers are experiments, not a proven fix.
        standard_launch = launch.replace(
            'set "SA6I_CLEAN_WIN7_SOFTWARE=1"', 'set "SA6I_CLEAN_WIN7_SOFTWARE="').replace(
            'set "QT_QUICK_BACKEND=software"', 'set "QT_QUICK_BACKEND="').replace(
            f'Sa6i-Link-Integrated-Test-{unique}', f'Sa6i-Link-Integrated-Standard-{unique}')
        (staged / 'Start Integrated Standard Rendering.cmd').write_bytes(standard_launch.encode('ascii'))
        (staged / 'READ FIRST - EXPERIMENT.txt').write_text(
            'EXPERIMENTAL INTEGRATION — NOT A FINAL PRODUCT\n\n'
            'This is a separate source build, not the published Sa6i Link app. '
            'Do not install it over an existing copy or use real accounts or important files.\n'
            'This package contains the FULL cleaner: some operations permanently delete '
            'files, empty the Recycle Bin, change startup entries, or run uninstallers. '
            'Use only a disposable environment with verified backups.\n'
            'To launch this experiment, use Start Integrated Test.cmd from this folder. '
            'On Windows 7, VxKex may need to be enabled separately for both '
            'nectarlink-desktop.exe and Sa6i Clean\\Sa6i Clean Integration.exe; '
            'this is not configured automatically and compatibility is not guaranteed.\n'
            'The test launcher requests Qt software rendering and passes --disable-gpu '
            'to the cleaner as an experimental clipping workaround; performance may suffer. '
            'The alternate Standard Rendering launcher clears both overrides and uses a '
            'separate test profile; neither path is verified on Windows 7.\n'
            'A separate application data path is used, but this is NOT a sandbox. '
            'The application and cleaner can still access normal user and OS paths.\n'
            'The included app-local cldapi.dll is the compatibility shim from the '
            'original Sa6i Link package. It disables phone-storage integration '
            'in Windows Explorer; it is not a full Cloud Files implementation.\n'
            'Windows 7/VxKex behavior, focus, rendering, process shutdown, cleanup '
            'safety and installed-app isolation are not validated. The executable header '
            'change does not implement missing Windows APIs. Never modify an existing '
            'VxKex configuration automatically.\n'
            'The cleaner is an unsigned packaged modification of Cleanly 0.2.0 by '
            '0xCodez, used with permission supplied by the user. Preserve its licenses.\n',
            encoding='utf-8')
        # Reserve a new destination atomically. Never replace an existing
        # directory, even an empty one. A failed move leaves this new partial
        # output for manual inspection instead of deleting unrelated files.
        output.mkdir()
        for entry in staged.iterdir():
            entry.rename(output / entry.name)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('desktop_dir', type=Path)
    parser.add_argument('cleaner_dir', type=Path)
    parser.add_argument('output_dir', type=Path)
    parser.add_argument('--win7-shim', type=Path, required=True,
                        help='the exact cldapi.dll from the supplied original Sa6i Link package')
    args = parser.parse_args()
    print('Created', package(args.desktop_dir, args.cleaner_dir, args.output_dir, args.win7_shim))
