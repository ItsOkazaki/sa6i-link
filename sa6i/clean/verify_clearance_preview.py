#!/usr/bin/env python3
"""Read-only integrity check for the exact header-clearance preview.

Compare a freshly assembled folder against the complete known base and update
ZIPs. No cleaner is launched, and matching files do not establish safety.
"""
import argparse
import hashlib
from pathlib import Path, PurePosixPath
import stat
import sys
from zipfile import BadZipFile, ZipFile

BASE_SHA256 = '068430f9c5ba9376a474134ba13db19817a93a0196a7f692101df40640459d50'
UPDATE_SHA256 = 'f5cf590a076d72275c0257ad8034bbd277819c7df114805b485214e4271b917d'
BASE_ROOT = 'Sa6i Link Unified Preview/'


def sha_stream(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(chunk)
    return digest.hexdigest()


def archive_files(archive, prefix):
    result = {}
    names = set()
    for info in archive.infolist():
        name = info.filename
        if not name.startswith(prefix):
            raise ValueError('Unexpected archive root: ' + name)
        relative = name[len(prefix):]
        if not relative:
            continue
        path = PurePosixPath(relative)
        if (relative.startswith('/') or '\\' in relative or ':' in relative or
                any(part in ('', '.', '..') for part in relative.rstrip('/').split('/'))):
            raise ValueError('Unsafe archive path: ' + name)
        key = str(path).casefold()
        if key in names:
            raise ValueError('Duplicate or case-colliding archive path: ' + name)
        names.add(key)
        mode = (info.external_attr >> 16) & 0xffff
        if stat.S_ISLNK(mode):
            raise ValueError('Archive contains a symbolic link: ' + name)
        if not info.is_dir():
            with archive.open(info) as stream:
                result[key] = (str(path), info.file_size, sha_stream(stream))
    return result


def verify(base, update, folder):
    """Return discrepancies; raise on unknown archives or unsafe archive data."""
    for path, expected in ((base, BASE_SHA256), (update, UPDATE_SHA256)):
        with path.open('rb') as stream:
            if sha_stream(stream) != expected:
                raise ValueError('Unknown archive: ' + str(path))
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('Preview must be a real directory')
    with ZipFile(base) as base_zip, ZipFile(update) as update_zip:
        expected = archive_files(base_zip, BASE_ROOT)
        # The update is overlaid at the root of the copied base folder.
        expected.update(archive_files(update_zip, ''))
    actual = {}
    errors = []
    for path in folder.rglob('*'):
        relative = path.relative_to(folder).as_posix()
        key = relative.casefold()
        if path.is_symlink():
            errors.append('Symbolic link: ' + relative)
        elif path.is_file():
            if key in actual:
                errors.append('Case-colliding file: ' + relative)
            else:
                actual[key] = path
        elif not path.is_dir():
            errors.append('Not a regular file or directory: ' + relative)
    for key, (name, size, digest) in expected.items():
        path = actual.pop(key, None)
        if path is None:
            errors.append('Missing: ' + name)
        else:
            try:
                if path.stat().st_size != size:
                    errors.append('Different: ' + name)
                else:
                    with path.open('rb') as stream:
                        if sha_stream(stream) != digest:
                            errors.append('Different: ' + name)
            except OSError as exc:
                errors.append('Cannot read {}: {}'.format(name, exc))
    for path in actual.values():
        errors.append('Unexpected: ' + path.relative_to(folder).as_posix())
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_zip', type=Path)
    parser.add_argument('update_zip', type=Path)
    parser.add_argument('preview_folder', type=Path)
    args = parser.parse_args()
    try:
        errors = verify(args.base_zip, args.update_zip, args.preview_folder)
    except (OSError, ValueError, RuntimeError, BadZipFile) as exc:
        print('Verification failed:', exc, file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(error)
        return 1
    print('All files match the known base and header-clearance update.')
    print('Integrity only: this does not test compatibility or cleanup safety.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
