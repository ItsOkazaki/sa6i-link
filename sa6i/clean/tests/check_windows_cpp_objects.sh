#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Compile the actual Windows C++ integration and its moc output to objects.
# This is NOT a linked app, a real Windows Qt SDK test, or an ABI guarantee.
# Linux cross-compiler inputs; examples and limitations in QT-HOST-PLAN.md.
set -euo pipefail

: "${SA6I_ZIG:?Path to Zig executable}"
: "${SA6I_MOC:?Path to Qt moc executable}"
: "${SA6I_QT_INCLUDE_DIRS:?Colon-separated Qt include roots}"
: "${SA6I_CXX_INCLUDE_DIR:?Include root containing rust/cxx.h}"
command -v nm >/dev/null || { echo 'nm is required' >&2; exit 1; }
[[ -x "$SA6I_ZIG" && -x "$SA6I_MOC" && -f "$SA6I_CXX_INCLUDE_DIR/rust/cxx.h" ]] || {
    echo 'Missing Zig, moc, or rust/cxx.h' >&2; exit 1;
}
IFS=: read -ra qt_roots <<< "$SA6I_QT_INCLUDE_DIRS"
includes=(-I"$SA6I_CXX_INCLUDE_DIR")
for dir in "${qt_roots[@]}"; do
    [[ -n "$dir" && -d "$dir" ]] || { echo "Invalid Qt include root: $dir" >&2; exit 1; }
    includes+=(-I"$dir")
done
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
WORK=$(mktemp -d "${TMPDIR:-/tmp}/sa6i-win-cpp-XXXXXX")
trap 'rm -rf "$WORK"' EXIT
flags=(-target x86_64-windows-gnu -std=c++17 -DWINVER=0x0a00 -Wno-ignored-attributes -c
       -I"$WORK" "${includes[@]}" -I"$ROOT/sa6i/clean" -I"$ROOT/desktop/app/cpp")
for enabled in 0 1; do
    printf '#define SA6I_CLEAN_EXPERIMENT %s\n' "$enabled" > "$WORK/sa6i_clean_config.h"
    "$SA6I_ZIG" c++ "${flags[@]}" "$ROOT/desktop/app/cpp/native_window.cpp" -o "$WORK/window-$enabled.o"
    nm -u "$WORK/window-$enabled.o" > "$WORK/undefined-$enabled.txt"
    if [[ "$enabled" == 0 ]]; then
        if grep -E 'QtEmbedAdapter|viewport_to_client' "$WORK/undefined-$enabled.txt"; then
            echo 'Unexpected cleaner reference in the ordinary window object' >&2; exit 1
        fi
    else
        grep -q 'QtEmbedAdapter' "$WORK/undefined-$enabled.txt"
        grep -q 'viewport_to_client' "$WORK/undefined-$enabled.txt"
    fi
done
"$SA6I_ZIG" c++ "${flags[@]}" "$ROOT/sa6i/clean/qt_embed_adapter.cpp" -o "$WORK/adapter.o"
# CxxQtBuilder builds its listed source files as C++, so exercise that mode.
for src in native_embed viewport_geometry; do
    "$SA6I_ZIG" c++ "${flags[@]}" -x c++ "$ROOT/sa6i/clean/$src.c" -o "$WORK/$src.o"
done
"$SA6I_MOC" "$ROOT/desktop/app/cpp/native_window.h" -o "$WORK/moc_window.cpp"
"$SA6I_MOC" "$ROOT/sa6i/clean/qt_embed_adapter.h" -o "$WORK/moc_adapter.cpp"
for unit in window adapter; do
    "$SA6I_ZIG" c++ "${flags[@]}" "$WORK/moc_$unit.cpp" -o "$WORK/moc_$unit.o"
done
printf '%s\n' 'Windows-target C++ and moc objects compiled; ordinary window has no cleaner references.' \
    'Objects were not linked or run. This is not a full Windows build or ABI/compatibility test.'
