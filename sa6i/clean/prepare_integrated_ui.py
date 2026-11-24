#!/usr/bin/env python3
"""Create a separate full-cleaner fixture with a frameless embedded window.

Only the exact inspected, branded Cleanly 0.2.0 candidate is accepted. This
changes window chrome, not cleanup behavior; it is neither a sandbox nor a
release build. Requires Node and @electron/asar 4.3.2 through npx.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

from build_candidate import header_hash, replace_exact, sha
from prepare_full_integration import ASAR_SHA as OUTPUT_ASAR_SHA, SOURCE_SHA as OUTPUT_EXE_SHA

SOURCE_EXE_SHA = 'a7b799c09a4748233095803d36d6453c43faed40ddf4d9d972a376884c1aadc7'
SOURCE_ASAR_SHA = '498f73db929e0c3564148ea93e59f28aeab0694642b639285bd4576b83f60112'
WINDOW_OPTIONS = 'title:"Sa6i Clean",titleBarStyle:"hidden",...r?{trafficLightPosition:{x:20,y:16}}:{titleBarOverlay:{color:"#00000000",symbolColor:w_().symbol,height:44}}'
FRAMELESS_OPTIONS = 'title:"Sa6i Clean",frame:!1'
THEME_OVERLAY = 'process.platform!=="darwin"&&ke.setTitleBarOverlay({color:"#00000000",symbolColor:r.symbol,height:44})'


def patch_main(main):
    # Preserve the renderer's own title/status bar. Only native window chrome
    # and theme updates for the now-absent native overlay are removed.
    replace_exact(main, WINDOW_OPTIONS, FRAMELESS_OPTIONS, 1)
    replace_exact(main, THEME_OVERLAY, 'void 0', 1)


def prepare(source, output):
    if source.is_symlink():
        raise ValueError('Symlinks are not allowed in the source')
    source, output = source.resolve(), output.absolute()
    if not source.is_dir() or output == source or source in output.parents or output in source.parents:
        raise ValueError('Source and destination must be separate directories')
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Refusing to overwrite {output}')
    if source.is_symlink() or any(p.is_symlink() for p in source.rglob('*')):
        raise ValueError('Symlinks are not allowed in the source')
    exe = source / 'Sa6i Clean.exe'
    asar = source / 'resources/app.asar'
    if sha(exe) != SOURCE_EXE_SHA or sha(asar) != SOURCE_ASAR_SHA:
        raise ValueError('Cleaner does not match the inspected source fixture')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.sa6i-ui-', dir=output.parent) as tmp:
        root = Path(tmp)
        app = root / 'app'
        subprocess.run(['npx', '--yes', '@electron/asar@4.3.2', 'extract', str(asar), str(app)], check=True)
        patch_main(app / 'dist-electron/main.js')
        staged = root / 'fixture'
        shutil.copytree(source, staged, ignore=lambda path, names: {'Sa6i Clean Integration.exe'} if Path(path) == source else set())
        patched_asar = staged / 'resources/app.asar'
        patched_asar.unlink()
        subprocess.run(['npx', '--yes', '@electron/asar@4.3.2', 'pack', str(app), str(patched_asar)], check=True)
        old = header_hash(asar).encode('ascii')
        new = header_hash(patched_asar).encode('ascii')
        patched_exe = staged / 'Sa6i Clean.exe'
        with patched_exe.open('r+b') as f:
            data = f.read()
            if data.count(old) != 1:
                raise ValueError('Expected exactly one ASAR integrity resource')
            offset = data.index(old)
            del data
            f.seek(offset)
            f.write(new)
        if sha(patched_exe) != OUTPUT_EXE_SHA or sha(patched_asar) != OUTPUT_ASAR_SHA:
            raise ValueError('Prepared cleaner differs from the pinned integrated fixture')
        # mkdir is an atomic refusal to replace an existing destination.
        output.mkdir()
        for item in staged.iterdir():
            item.rename(output / item.name)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = prepare(args.source, args.output)
    print('Created', result)
    print('Executable SHA-256:', sha(result / 'Sa6i Clean.exe'))
    print('ASAR SHA-256:', sha(result / 'resources/app.asar'))
    print('Experimental only; cleanup remains destructive and Windows behavior is unverified.')
