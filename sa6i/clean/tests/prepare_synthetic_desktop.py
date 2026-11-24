#!/usr/bin/env python3
"""Patch only an ephemeral CI desktop copy to pin an inert test window.

The output is not a release executable and must never be distributed. The
real Sa6i Clean executable, ASAR and production source are not modified.
"""
from hashlib import sha256
from pathlib import Path
import argparse

DESKTOP_SHA = 'bbe4bb2d4b2f898ac38f7ac0947ecf61483705e0d238ec0e813552545bc6bcbe'
PINS = (
    ('04f2c19923f356fa83f7f5a5e7d074ca3df70020e755204ab63c023d5afd70e9', 'Sa6i Clean Integration.exe'),
    ('498f73db929e0c3564148ea93e59f28aeab0694642b639285bd4576b83f60112', 'resources/app.asar'),
)

# Prior unthemed artifact pins, retained for historical investigations.
CURRENT_PINS = (
    ('435923fe5a7404feef6bdf242b444dda5def1a05d68a720038e41294086dbb4e', 'Sa6i Clean Integration.exe'),
    ('62b7546a12ddac85b6fc506b0fb151acd15944ce3a809f9f4c8390965ef1080a', 'resources/app.asar'),
)
THEMED_PINS = (
    ('e991d57efbb8de204a7fb9e9f5b3ef5fe34531e37e77556f66f079545a866a3f', 'Sa6i Clean Integration.exe'),
    ('b3af2dd8355194905fc929ccd1d40dcaa78542208cc4b0d0612c50bf9d93e83f', 'resources/app.asar'),
)


def main(desktop: Path, fixture: Path, desktop_sha=DESKTOP_SHA, pins=PINS):
    data = desktop.read_bytes()
    if sha256(data).hexdigest() != desktop_sha:
        raise SystemExit('Desktop binary does not match the expected CI artifact')
    if 'Sa6i Clean Integration.exe'.encode('utf-16le') not in data:
        raise SystemExit('Expected fixture name is missing')
    for original, name in pins:
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('desktop', type=Path)
    parser.add_argument('fixture', type=Path)
    parser.add_argument('--desktop-sha', default=DESKTOP_SHA,
                        help='SHA-256 of the trusted CI artifact being tested')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--current-pins', action='store_true',
                       help='use the prior full-cleaner artifact pins')
    group.add_argument('--themed-pins', action='store_true',
                       help='use the new experimental themed-fixture pins')
    args = parser.parse_args()
    pins = THEMED_PINS if args.themed_pins else CURRENT_PINS if args.current_pins else PINS
    main(args.desktop, args.fixture, args.desktop_sha, pins)
