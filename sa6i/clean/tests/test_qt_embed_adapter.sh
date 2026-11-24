#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Linux-only development test: uses real QtCore and fake Win32/crypto.
# QT_ROOT must provide QtCore headers, libQt6Core, and libexec/moc.
# RUN_QML_TEST=1 additionally requires QT_RUNTIME_LIB and PySide6 using the
# same Qt runtime; set up Python/library paths externally. Never ship the shim.
set -eu
: "${QT_ROOT:?point QT_ROOT to a Qt6 build/install tree}"
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
cd "$ROOT"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/sa6i-adapter-test.XXXXXX")
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
CXX=${CXX:-c++}
CC=${CC:-cc}
"$QT_ROOT/libexec/moc" sa6i/clean/qt_embed_adapter.h -o "$WORK/moc_qt_embed_adapter.cpp"
"$CC" -std=c11 -fPIC -Wall -Wextra -Werror -pedantic -D_POSIX_C_SOURCE=200809L -DSA6I_SLOW_TEST -I sa6i/clean/tests/win32 \
    -c sa6i/clean/tests/qt_adapter_win32_sim.c -o "$WORK/sim.o"
"$CXX" -std=c++17 -fPIC -Wall -Wextra -Werror -I "$QT_ROOT/include" -I "$QT_ROOT/include/QtCore" \
    -I sa6i/clean/tests/win32 -DSA6I_EMBED_TEST sa6i/clean/qt_embed_adapter.cpp \
    "$WORK/moc_qt_embed_adapter.cpp" sa6i/clean/tests/test_qt_embed_adapter.cpp "$WORK/sim.o" \
    -L "$QT_ROOT/lib" -lQt6Core -Wl,-rpath,"$QT_ROOT/lib" -o "$WORK/fake-test"
"$WORK/fake-test"
"$CXX" -std=c++17 -fPIC -Wall -Wextra -Werror -I "$QT_ROOT/include" -I "$QT_ROOT/include/QtCore" \
    sa6i/clean/qt_embed_adapter.cpp "$WORK/moc_qt_embed_adapter.cpp" \
    sa6i/clean/tests/test_qt_embed_unsupported.cpp -L "$QT_ROOT/lib" -lQt6Core \
    -Wl,-rpath,"$QT_ROOT/lib" -o "$WORK/unsupported-test"
"$WORK/unsupported-test"
if [ "${RUN_QML_TEST:-0}" = 1 ]; then
    : "${QT_RUNTIME_LIB:?point QT_RUNTIME_LIB to the PySide6 Qt library directory}"
    "$CXX" -std=c++17 -shared -fPIC -Wall -Wextra -Werror -I "$QT_ROOT/include" -I "$QT_ROOT/include/QtCore" \
        -I sa6i/clean/tests/win32 -DSA6I_EMBED_TEST sa6i/clean/qt_embed_adapter.cpp \
        "$WORK/moc_qt_embed_adapter.cpp" sa6i/clean/tests/qt_adapter_test_exports.cpp "$WORK/sim.o" \
        -L "$QT_RUNTIME_LIB" -Wl,-l:libQt6Core.so.6 -Wl,-rpath,"$QT_RUNTIME_LIB" -o "$WORK/libtest_adapter.so"
    SA6I_QT_ADAPTER_TEST_LIB="$WORK/libtest_adapter.so" python3 -m unittest -v \
        sa6i.clean.test_adapter_gate sa6i.clean.test_app_close_wiring sa6i.clean.test_tray_reactivation
fi
