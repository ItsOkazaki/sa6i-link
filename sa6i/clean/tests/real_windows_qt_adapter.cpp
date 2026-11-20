// SPDX-License-Identifier: GPL-3.0-or-later
// Real Qt adapter + real Win32 APIs against an inert synthetic window.
// Does not test Electron, the full QML app, Windows 7, or cleanup safety.
#include "qt_embed_adapter.h"
#include <QtCore/QCoreApplication>
#include <QtCore/QElapsedTimer>
#include <QtCore/QEventLoop>
#include <QtCore/QThread>
#include <QtCore/QString>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstdlib>

static void tick()
{
    QCoreApplication::processEvents(QEventLoop::AllEvents, 25);
    MSG msg;
    while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    QThread::msleep(20);
}

static bool waitAttached(QtEmbedAdapter &adapter)
{
    QElapsedTimer timer; timer.start();
    while (timer.elapsed() < 12000) {
        tick();
        if (adapter.status() == QStringLiteral("attached")) return true;
        if (adapter.status() == QStringLiteral("unattached") ||
            (adapter.initialized() && !adapter.processTracked())) return false;
    }
    return false;
}

static bool waitClosed(QtEmbedAdapter &adapter)
{
    QElapsedTimer timer; timer.start();
    while (timer.elapsed() < 12000) {
        tick();
        if (adapter.requestClose()) return !adapter.processTracked();
    }
    return false;
}

static bool waitVisible(HWND parent, bool visible)
{
    QElapsedTimer timer; timer.start();
    while (timer.elapsed() < 4000) {
        tick();
        HWND child = GetWindow(parent, GW_CHILD);
        if (child && (!!IsWindowVisible(child) == visible)) return true;
    }
    return false;
}

#define CHECK(condition, description) do { if (!(condition)) { \
    std::fprintf(stderr, "FAIL %s status=%s tracked=%d pending=%d error=%lu\n", description, \
        adapter.status().toUtf8().constData(), adapter.processTracked(), adapter.launchPending(), \
        static_cast<unsigned long>(adapter.error())); std::exit(1); } } while (0)

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    if (app.arguments().size() != 2) return 2;
    const QString fixture = app.arguments().at(1);
    HWND parent = CreateWindowExW(0, L"STATIC", L"Qt synthetic host test",
        WS_OVERLAPPEDWINDOW, 40, 40, 1000, 800, nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
    if (!parent) { std::fprintf(stderr, "Could not create test parent\n"); return 1; }
    ShowWindow(parent, SW_SHOW);
    QtEmbedAdapter adapter;
    CHECK(adapter.supported(), "adapter support");
    CHECK(adapter.bindNativeParent(reinterpret_cast<quintptr>(parent)), "bind parent");
    CHECK(adapter.setRect(10, 20, 500, 350), "set viewport");
    CHECK(adapter.setSelected(true), "select viewport");
    CHECK(adapter.start(fixture), "schedule launch");
    CHECK(adapter.processTracked() && adapter.launchPending(), "track pending launch");
    CHECK(!adapter.start(fixture), "reject duplicate launch");
    CHECK(waitAttached(adapter), "worker handoff and attach");
    CHECK(waitVisible(parent, true), "child visible");
    CHECK(adapter.setSelected(false) && waitVisible(parent, false), "hide child");
    CHECK(adapter.setSelected(true) && waitVisible(parent, true), "show child");
    CHECK(adapter.setRect(25, 30, 650, 475), "queue resize");
    CHECK(!adapter.requestClose(), "close waits for process");
    CHECK(waitClosed(adapter), "quit child and reap");
    std::puts("PASS: real Qt adapter launch, handoff, attach, hide, show, close");

    CHECK(adapter.bindNativeParent(reinterpret_cast<quintptr>(parent)), "rebind closed host");
    CHECK(adapter.setRect(10, 20, 500, 350), "second viewport");
    CHECK(adapter.start(fixture), "second launch");
    CHECK(adapter.launchPending() && adapter.processTracked(), "second launch tracked");
    CHECK(!adapter.requestClose(), "close during launch waits");
    CHECK(waitClosed(adapter), "close during launch and reap");
    std::puts("PASS: real Qt adapter close during launch");
    DestroyWindow(parent);
    return 0;
}
