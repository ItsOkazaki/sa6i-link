"""Pack the Sa6i Clean branding patch for delivery.

The package is two small script folders plus the prepared ``app.asar``. The
bundle is produced by ``debrand_cleaner.py`` (plus the junction guard from
``harden_cleaner.py``) and is checked here by hash, so a stale or partly
branded bundle can never be shipped by accident.

Usage::

    python sa6i/clean/delivery/build_delivery.py \
        --asar /tmp/clean/v5.asar --out "/tmp/clean/pkg/Sa6i Clean Branding v5.zip"
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import zipfile

HERE = pathlib.Path(__file__).resolve().parent

#: SHA-256 of the verified debranded bundle.
EXPECTED_ASAR_SHA = "2d163de5f5f862da2087579d8920796c970528a08d8bad9b682697f79050d2e9"

#: Where the cleaner files go, and where the retarget files go. Delivering the
#: two groups in numbered folders is what stopped "copy the three files" from
#: landing app.asar in the wrong place.
CLEAN_FOLDER = "1 - into the Sa6i Clean folder"
CANDIDATE_FOLDER = "2 - into the candidate folder"

#: (source beside this file, name inside the ZIP).
PAYLOAD = (
    ("Install-Sa6i-Clean-Patch.ps1", f"{CLEAN_FOLDER}/Install-Sa6i-Clean-Patch.ps1"),
    ("Apply Sa6i Clean Patch.cmd", f"{CLEAN_FOLDER}/Apply Sa6i Clean Patch.cmd"),
    ("Retarget-Sa6i-Clean-Digests.ps1", f"{CANDIDATE_FOLDER}/Retarget-Sa6i-Clean-Digests.ps1"),
    ("Retarget Sa6i Clean.cmd", f"{CANDIDATE_FOLDER}/Retarget Sa6i Clean.cmd"),
    ("README.txt", "README.txt"),
)

#: The bundle travels with the cleaner files.
ASAR_ENTRY = f"{CLEAN_FOLDER}/app.asar"

#: Oldest timestamp a ZIP entry may carry without upsetting unzip tools.
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def to_crlf(data: bytes) -> bytes:
    """Return ``data`` with Windows line endings.

    The text files are stored in this repository with LF endings. Delivery
    happens on Windows, where ``cmd.exe`` mis-parses LF-only batch files and
    older Notepad shows them as one long line, so the packaged copies always
    use CRLF no matter how they were checked out.
    """
    return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def sha256_of(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(asar: pathlib.Path, out: pathlib.Path) -> None:
    if not asar.is_file():
        raise SystemExit(f"missing bundle: {asar}")
    actual = sha256_of(asar)
    if actual != EXPECTED_ASAR_SHA:
        raise SystemExit(
            f"bundle hash mismatch\n  expected {EXPECTED_ASAR_SHA}\n  actual   {actual}"
        )

    entries: list[tuple[str, bytes]] = []
    for source_name, entry_name in PAYLOAD:
        source = HERE / source_name
        if not source.is_file():
            raise SystemExit(f"missing delivery file: {source}")
        entries.append((entry_name, to_crlf(source.read_bytes())))
    entries.append((ASAR_ENTRY, asar.read_bytes()))

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry_name, data in entries:
            info = zipfile.ZipInfo(entry_name, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)

    print(f"wrote {out} ({out.stat().st_size} bytes)")
    for entry_name, data in entries:
        print(f"  {entry_name:58} {len(data):>9} bytes")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asar", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    build(args.asar, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
