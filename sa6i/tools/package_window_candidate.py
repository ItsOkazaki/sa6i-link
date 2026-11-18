#!/usr/bin/env python3
"""Make a separate, untested title-bar candidate from the exact v8 test ZIP.

This is a version-locked QML workaround, not the C++ source change. It never
modifies the input ZIP. Test on both Windows 7 and Windows 11 before release.
"""

import hashlib
import struct
import sys
import zlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ZIP_HASH = "c5625d2a20d5cf4c3bb9f147f1a8ca32aad934fcebabd4e38a6aeaf39105236d"
APP_HASH = "f2a7598aa067eb1ed19628e73b8c958d97db3bb8e09c424a6ab14f393e33d19c"
LAUNCHER_HASH = "3862e83cbdcd08022ba3bf9a23feb48506842808d8e2eef2590a4d92924d1b39"
ROOT = "Sa6i-Link/"
APP = ROOT + "Sa6i-Link-Win7-UI-v8.exe"
LAUNCHER = ROOT + "Start Sa6i Link v8.exe"
APP_NEW = ROOT + "Sa6i Link App.exe"
LAUNCHER_NEW = ROOT + "Sa6i Link.exe"
QML_OFFSET = 0x1D53D2D
QML_CAPACITY = 9317  # reserved compressed-resource space from the v8 patch


def digest(data):
    return hashlib.sha256(data).hexdigest()


def patched_app(data):
    if digest(data) != APP_HASH:
        raise ValueError("Unexpected app executable; refusing to patch")
    buf = bytearray(data)
    length = struct.unpack_from(">I", buf, QML_OFFSET - 8)[0] - 4
    original = zlib.decompress(buf[QML_OFFSET:QML_OFFSET + length]).decode("utf-8")
    old = "Component.onCompleted: {\nfollowBackdrop()"
    new = (
        "Component.onCompleted: {\n"
        "if (Qt.platform.os === \"windows\" && window.systemBackdropSupported)\n"
        "window.flags = (window.flags & ~Qt.ExpandedClientAreaHint) | Qt.FramelessWindowHint\n"
        "followBackdrop()"
    )
    if original.count(old) != 1:
        raise ValueError("Unexpected MainWindow source; refusing to patch")
    modified = original.replace(old, new)
    compressed = zlib.compress(modified.encode("utf-8"), 9)
    if len(compressed) > QML_CAPACITY:
        raise ValueError("Patched QML exceeds its reserved resource space")
    # The v8 patch already redirects the cached MainWindow unit to NainWindow,
    # so Qt falls back to the edited source resource.
    marker = "/qt/qml/app/nectarlink/qml/NainWindow.qml".encode("utf-16le")
    if buf.count(marker) != 1:
        raise ValueError("Expected QML cache fallback marker not found")
    struct.pack_into(">I", buf, QML_OFFSET - 8, len(compressed) + 4)
    struct.pack_into(">I", buf, QML_OFFSET - 4, len(modified.encode("utf-8")))
    buf[QML_OFFSET:QML_OFFSET + QML_CAPACITY] = compressed.ljust(QML_CAPACITY, b"\0")
    return bytes(buf)


def patched_launcher(data):
    if digest(data) != LAUNCHER_HASH:
        raise ValueError("Unexpected launcher; refusing to patch")
    old = "%ls\\Sa6i-Link-Win7-UI-v8.exe".encode("utf-16le") + b"\0\0"
    new = "%ls\\Sa6i Link App.exe".encode("utf-16le") + b"\0\0"
    if len(new) > len(old) or data.count(old) != 1:
        raise ValueError("Unexpected launcher target; refusing to patch")
    return data.replace(old, new.ljust(len(old), b"\0"), 1)


def package(input_path, output_path):
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Input and output must be different files")
    if digest(input_path.read_bytes()) != ZIP_HASH:
        raise ValueError("Unexpected input ZIP; refusing to patch")
    if output_path.exists():
        raise FileExistsError("Refusing to overwrite an existing output")
    start = (
        "Sa6i Link - experimental Windows test\n\n"
        "This separate test package is not an installer and has not been tested on Windows. "
        "It contains an unverified Windows 11 title-bar workaround. It may affect window "
        "controls, resizing or Snap. Keep your original working installation and back up "
        "shared settings and pairings.\n\n"
        "Extract the entire ZIP to a separate folder. If your system requires VxKex, "
        "enable it for Sa6i Link App.exe in this extracted folder; path-specific settings "
        "may not carry over. Then run Sa6i Link.exe. If VxKex does not stay enabled or "
        "the app fails, use your original working copy. Do not replace system DLLs "
        "or use the original updater.\n"
    )
    with ZipFile(input_path) as src, ZipFile(output_path, "x", ZIP_DEFLATED, compresslevel=6) as dst:
        names = set(src.namelist())
        if not {APP, LAUNCHER, ROOT + "START-HERE.txt"} <= names:
            raise ValueError("Required files are missing")
        app = patched_app(src.read(APP))
        launcher = patched_launcher(src.read(LAUNCHER))
        for entry in src.infolist():
            if entry.filename in {APP, LAUNCHER, ROOT + "START-HERE.txt"}:
                continue
            dst.writestr(entry, src.read(entry.filename))
        dst.writestr(APP_NEW, app)
        dst.writestr(LAUNCHER_NEW, launcher)
        dst.writestr(ROOT + "START-HERE.txt", start.encode("utf-8"))
    with ZipFile(output_path) as dst:
        if dst.testzip() is not None:
            raise ValueError("Output ZIP failed integrity check")
        assert dst.read(APP_NEW) == app and dst.read(LAUNCHER_NEW) == launcher
        print("app sha256", digest(app))
        print("launcher sha256", digest(launcher))
    print("zip sha256", digest(output_path.read_bytes()))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: package_window_candidate.py INPUT.zip OUTPUT.zip")
    package(Path(sys.argv[1]), Path(sys.argv[2]))
