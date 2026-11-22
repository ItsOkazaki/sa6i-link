"""Pack the Sa6i Clean debranding patch for delivery.

The patch is three text files plus one prepared ``app.asar``. The bundle is
produced by ``debrand_cleaner.py`` (plus the junction guard from
``harden_cleaner.py``) and is checked here by hash, so a stale or unbranded
bundle can never be shipped by accident.

Usage::

    python sa6i/clean/delivery/build_delivery.py \
        --asar /tmp/clean/pkg/app.asar --out "/tmp/clean/pkg/Sa6i Clean Debranded Bundle v3.zip"
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import zipfile

HERE = pathlib.Path(__file__).resolve().parent

#: SHA-256 of the verified debranded bundle.
EXPECTED_ASAR_SHA = "ea12336539260cfda7c409882bda14bbe9704f55c66c916db34fbe7b0d7f0fac"

#: Files copied into the delivery ZIP, in the order they are listed.
PAYLOAD = (
    "Install-Sa6i-Clean-Patch.ps1",
    "Apply Sa6i Clean Patch.cmd",
    "README.txt",
)

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
    for name in PAYLOAD:
        source = HERE / name
        if not source.is_file():
            raise SystemExit(f"missing delivery file: {source}")
        entries.append((name, to_crlf(source.read_bytes())))
    entries.append(("app.asar", asar.read_bytes()))

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)

    print(f"wrote {out} ({out.stat().st_size} bytes)")
    for name, data in entries:
        print(f"  {name:34} {len(data):>9} bytes")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asar", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    build(args.asar, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
