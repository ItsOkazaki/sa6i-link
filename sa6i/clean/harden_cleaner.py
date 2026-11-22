#!/usr/bin/env python3
"""Add the Sa6i cache-root guard to the packaged cleaner without rebuilding it.

The packaged cleaner is a binary-patched Electron app, so the guard is inserted
into its minified main-process bundle with exact, counted string replacements,
mirroring `harden_upstream.py`. The ASAR is repacked and the executable's
embedded ASAR-integrity hash is updated, exactly as the branding pipeline does.

Nothing is executed: the app is never launched, and no installation is touched.
Inputs are hash-locked to the tested candidate.
"""
import argparse
import hashlib
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

CLEANER_EXE_SHA = 'e991d57efbb8de204a7fb9e9f5b3ef5fe34531e37e77556f66f079545a866a3f'
CLEANER_ASAR_SHA = 'b3af2dd8355194905fc929ccd1d40dcaa78542208cc4b0d0612c50bf9d93e83f'

FUNC = 'async function dS(r,i,e={}){'
FUNC_BODY = 'try{let n=await st.lstat(r);if(n.isSymbolicLink()||!re(i,r))'
SNIPPET = Path(__file__).resolve().parent / 'guard_snippet.js'
SNIPPET_SHA = 'a5ad5d41643a7e0eff6c57a125d253cdf2dd236cfb55b98c10d8aeb1f5454e62'


def helper_snippet():
    """The tested minified guard, without its comment lines."""
    code = '\n'.join(line for line in SNIPPET.read_text(encoding='utf-8').splitlines()
                      if line.strip() and not line.lstrip().startswith('//'))
    if hashlib.sha256((code + '\n').encode('utf-8')).hexdigest() != SNIPPET_SHA:
        raise ValueError('guard_snippet.js does not match the reviewed guard')
    return code


GUARD = 'if(!await Sa6iUnredirectedRoot(i))return t.refused=!0,t;'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def header_hash(path):
    with Path(path).open('rb') as f:
        _, _, _, size = struct.unpack('<IIII', f.read(16))
        if not 0 < size < 20_000_000:
            raise ValueError('Invalid ASAR header')
        header = f.read(size)
        if len(header) != size:
            raise ValueError('Truncated ASAR header')
        return hashlib.sha256(header).hexdigest()


def patch_main(main):
    text = main.read_text(encoding='utf-8')
    if 'Sa6iUnredirectedRoot' in text:
        raise ValueError('Guard already present')
    if text.count(FUNC) != 1 or text.count(FUNC_BODY) != 1:
        raise ValueError('Unexpected packaged bundle layout')
    text = text.replace(FUNC, helper_snippet() + FUNC, 1)
    text = text.replace(FUNC_BODY, 'try{' + GUARD + 'let n=await st.lstat(r);if(n.isSymbolicLink()||!re(i,r))', 1)
    # Force LF so the bundle is identical on any build host.
    main.write_text(text, encoding='utf-8', newline='\n')


def harden(exe_path, asar_path, output_dir):
    exe_path, asar_path = Path(exe_path).resolve(), Path(asar_path).resolve()
    output_dir = Path(output_dir).absolute()
    if output_dir.exists():
        raise FileExistsError(f'Refusing to overwrite {output_dir}')
    if sha(exe_path) != CLEANER_EXE_SHA or sha(asar_path) != CLEANER_ASAR_SHA:
        raise ValueError('Inputs do not match the tested candidate cleaner')
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.sa6i-harden-', dir=output_dir.parent) as tmp:
        work = Path(tmp)
        app = work / 'app'
        subprocess.run(['npx', '--yes', '@electron/asar@4.3.2', 'extract', str(asar_path), str(app)],
                       check=True, stdout=subprocess.DEVNULL)
        patch_main(app / 'dist-electron/main.js')
        new_asar = work / 'app.asar'
        subprocess.run(['npx', '--yes', '@electron/asar@4.3.2', 'pack', str(app), str(new_asar)],
                       check=True, stdout=subprocess.DEVNULL)
        old, new = header_hash(asar_path).encode('ascii'), header_hash(new_asar).encode('ascii')
        new_exe = work / exe_path.name
        shutil.copyfile(exe_path, new_exe)
        with new_exe.open('r+b') as f:
            data = f.read()
            if data.count(old) != 1:
                raise ValueError('Expected exactly one ASAR integrity resource')
            offset = data.index(old)
            del data
            f.seek(offset)
            f.write(new)
        output_dir.mkdir()
        shutil.move(str(new_exe), output_dir / exe_path.name)
        shutil.move(str(new_asar), output_dir / 'app.asar')
    return output_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('exe', type=Path)
    parser.add_argument('asar', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    out = harden(args.exe, args.asar, args.output)
    print('Hardened cleaner written to', out)
    print('Executable SHA-256:', sha(out / args.exe.name))
    print('ASAR SHA-256:', sha(out / 'app.asar'))
    print('Experimental build: cleaning behaviour has not been validated in the app.')


if __name__ == '__main__':
    main()
