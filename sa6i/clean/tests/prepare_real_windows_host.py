#!/usr/bin/env python3
"""Create a test-only copy pinned to an inert synthetic process, not Cleanly.

This helper never changes native_embed.c or the production fixture pins. It
makes a standalone temporary copy for the Windows native-host smoke test.
"""
import hashlib
from pathlib import Path
import re
import sys


def bytes_literal(path):
    return ','.join(f'0x{x:02x}' for x in hashlib.sha256(path.read_bytes()).digest())


def main(work: Path):
    work = work.resolve(strict=True)
    fixture = work / 'fixture'
    executable = fixture / 'Sa6i Test Window.exe'
    asar = fixture / 'resources' / 'app.asar'
    if not executable.is_file() or not asar.is_file():
        raise SystemExit('Synthetic test fixture is incomplete')
    source = (Path(__file__).resolve().parents[1] / 'native_embed.c').read_text(encoding='utf-8')
    block = (
        '#define CLEAN_EXE_NAME L"\\\\Sa6i Test Window.exe"\n'
        f'static const BYTE expected_exe[32] = {{{bytes_literal(executable)}}};\n'
        f'static const BYTE expected_asar[32] = {{{bytes_literal(asar)}}};\n'
    )
    pattern = r'#if SA6I_CLEAN_FULL_FIXTURE\n.*?\n#endif\n(?=\nstatic BOOL verify)'
    result, count = re.subn(pattern, lambda _: block, source, flags=re.DOTALL)
    if count != 1:
        raise SystemExit('Unexpected source layout; refusing to rewrite test copy')
    (work / 'native_embed_real_test.c').write_text(result, encoding='utf-8')
    (work / 'sa6i_clean_config.h').write_text('#define SA6I_CLEAN_FULL_FIXTURE 0\n', encoding='ascii')
    print('Prepared test-only backend with hashes for the synthetic fixture.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: prepare_real_windows_host.py WORK_DIR')
    main(Path(sys.argv[1]))
