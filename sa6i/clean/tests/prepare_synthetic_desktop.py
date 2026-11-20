#!/usr/bin/env python3
"""Patch only an ephemeral CI desktop copy to pin an inert test window.

The output is not a release executable and must never be distributed. The
real Sa6i Clean executable, ASAR and production source are not modified.
"""
from hashlib import sha256
from pathlib import Path
import sys

DESKTOP_SHA = '3539aa09472b9d0f65c8b4ce546969cbd34c90c4359399880beb84486b5cb1bb'
PINS = (
    ('04f2c19923f356fa83f7f5a5e7d074ca3df70020e755204ab63c023d5afd70e9', 'Sa6i Clean Integration.exe'),
    ('498f73db929e0c3564148ea93e59f28aeab0694642b639285bd4576b83f60112', 'resources/app.asar'),
)


def main(desktop: Path, fixture: Path):
    data = desktop.read_bytes()
    if sha256(data).hexdigest() != DESKTOP_SHA:
        raise SystemExit('Desktop binary does not match the known CI artifact')
    if 'Sa6i Clean Integration.exe'.encode('utf-16le') not in data:
        raise SystemExit('Expected fixture name is missing')
    for original, name in PINS:
        needle = bytes.fromhex(original)
        if data.count(needle) != 1:
            raise SystemExit(f'Expected exactly one pin for {name}')
        content = (fixture / name).read_bytes()
        data = data.replace(needle, sha256(content).digest(), 1)
    output = desktop.with_name('synthetic-test-desktop.exe')
    if output.exists():
        raise SystemExit('Refusing to overwrite test binary')
    output.write_bytes(data)
    print('Prepared synthetic-test-only desktop; never distribute this binary.')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: prepare_synthetic_desktop.py DESKTOP_EXE FIXTURE_DIR')
    main(Path(sys.argv[1]), Path(sys.argv[2]))
