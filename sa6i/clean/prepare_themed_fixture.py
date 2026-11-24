#!/usr/bin/env python3
"""Build a separate themed cleaner fixture from the exact integration fixture.

This prepares a candidate, not a release and not a replacement for any app.
It requires a desktop build whose allowlisted hashes match this fixture; old
desktop builds cannot launch it. The fixture initializes its color mode from
the host's fixed command-line switch; later changes do not automatically
propagate. Cleanup behavior and Windows 7 compatibility are unchanged.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

from build_candidate import header_hash, replace_exact, sha
from prepare_full_integration import ASAR_SHA, OUTPUT_NAME, OUTPUT_SHA
from prepare_theme import apply_to_extracted

THEMED_EXE_SHA = 'e991d57efbb8de204a7fb9e9f5b3ef5fe34531e37e77556f66f079545a866a3f'
THEMED_ASAR_SHA = 'b3af2dd8355194905fc929ccd1d40dcaa78542208cc4b0d0612c50bf9d93e83f'

# Only the default color mode for a fresh, isolated profile changes. Without
# a host-provided switch, the cleaner retains its original system default.
OLD_DEFAULT = 'var Kx={aiProvider:"claude",background:"mist",theme:"system",'
NEW_DEFAULT = ('var Kx={aiProvider:"claude",background:"mist",theme:'
               'process.argv.includes("--sa6i-theme-dark")?"dark":'
               'process.argv.includes("--sa6i-theme-light")?"light":"system",')


def apply_host_theme(extracted):
    replace_exact(extracted / 'dist-electron/main.js', OLD_DEFAULT, NEW_DEFAULT, 1)


def prepare(source, output):
    source, output = Path(source).absolute(), Path(output).absolute()
    if source.is_symlink() or not source.is_dir():
        raise ValueError('Source must be an existing non-symlink directory')
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Refusing to overwrite {output}')
    source_real, output_real = source.resolve(), output.resolve()
    if source_real == output_real or source_real in output_real.parents or output_real in source_real.parents:
        raise ValueError('Source and output must be separate directories')
    if any(p.is_symlink() for p in source.rglob('*')):
        raise ValueError('Symlinks are not allowed in the fixture')
    if sha(source / OUTPUT_NAME) != OUTPUT_SHA or sha(source / 'resources/app.asar') != ASAR_SHA:
        raise ValueError('Source does not match the pinned integration fixture')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.sa6i-themed-', dir=output.parent) as work:
        work = Path(work)
        extracted, stage = work / 'extracted', work / 'fixture'
        source_asar = source / 'resources/app.asar'
        subprocess.run(['npx', '--yes', '@electron/asar@4.3.2', 'extract', str(source_asar), str(extracted)], check=True)
        apply_to_extracted(extracted)
        apply_host_theme(extracted)
        shutil.copytree(source, stage, ignore=lambda path, names: {'Sa6i Clean.exe'} if Path(path) == source else set())
        new_asar = stage / 'resources/app.asar'
        new_asar.unlink()
        subprocess.run(['npx', '--yes', '@electron/asar@4.3.2', 'pack', str(extracted), str(new_asar)], check=True)
        old, new = header_hash(source_asar).encode('ascii'), header_hash(new_asar).encode('ascii')
        exe = stage / OUTPUT_NAME
        with exe.open('r+b') as f:
            content = f.read()
            if content.count(old) != 1:
                raise ValueError('Expected exactly one ASAR integrity resource in the executable')
            offset = content.index(old)
            del content
            f.seek(offset)
            f.write(new)
        if sha(exe) != THEMED_EXE_SHA or sha(new_asar) != THEMED_ASAR_SHA:
            raise ValueError('Prepared themed fixture does not match its pinned checksums')
        # Never replace an existing directory; reserve it only once all inputs
        # have been checked and the new fixture fully assembled.
        output.mkdir()
        for item in stage.iterdir():
            item.rename(output / item.name)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = prepare(args.source, args.output)
    print('Created experimental fixture:', result)
    print('Executable SHA-256:', sha(result / OUTPUT_NAME))
    print('ASAR SHA-256:', sha(result / 'resources/app.asar'))
    print('Not release-ready: matching host build, live theme changes, rendering and Windows 7 require validation.')
