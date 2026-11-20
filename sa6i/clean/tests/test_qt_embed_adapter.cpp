// SPDX-License-Identifier: GPL-3.0-or-later
// QtCore adapter + real C backend under deterministic fake Win32/crypto.
// Not a Windows integration, real hash or security test.
#include "../qt_embed_adapter.h"
#include "../native_embed.h"
#include <QtCore/QCoreApplication>
#include <QtCore/QEventLoop>
#include <QtCore/QTimer>
#include <cassert>
#include <cstdio>
#include <thread>

extern "C" {
void simulation_reset(void);
void simulation_make_window(void);
void simulation_exit(void);
void simulation_block_reads(void);
int simulation_read_waiting(void);
void simulation_release_reads(void);
void simulation_fail_launch(void);
int simulation_starts(void);
int simulation_close_messages(void);
int simulation_show(void);
int simulation_show_requests(void);
long simulation_rect_left(void);
long simulation_rect_bottom(void);
}
static void timer_wait(int ms) {
    QEventLoop loop;
    QTimer::singleShot(ms, &loop, &QEventLoop::quit);
    loop.exec();
}
static void wait_for_read() {
    for (int i = 0; i < 300 && !simulation_read_waiting(); ++i) timer_wait(10);
    assert(simulation_read_waiting());
}
static void wait_for_handoff(QtEmbedAdapter &a) {
    for (int i = 0; i < 300 && a.status() == "launching"; ++i) timer_wait(10);
    assert(a.status() != "launching");
}
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    simulation_reset();
    QtEmbedAdapter a;
    int changes = 0;
    QObject::connect(&a, &QtEmbedAdapter::changed, [&] { ++changes; });
    assert(a.supported() && !a.initialized() && a.status() == "unbound");
    assert(!a.start("C:/test") && a.requestClose());
    assert(!a.bindNativeParent(0));
    assert(a.bindNativeParent(1) && a.initialized() && a.status() == "idle");
    bool wrong_thread_close = true, wrong_thread_start = true, wrong_thread_bind = true;
    std::thread wrong_thread([&] {
        wrong_thread_close = a.requestClose();
        wrong_thread_start = a.start("C:/test");
        wrong_thread_bind = a.bindNativeParent(1);
        a.poll();
    });
    wrong_thread.join();
    assert(!wrong_thread_close && !wrong_thread_start && !wrong_thread_bind);
    assert(a.status() == "idle");
    assert(!a.setRect(-1, 0, 5, 5) && a.error() == ERROR_INVALID_PARAMETER);
    assert(a.setRect(10, 20, 300, 400) && a.setSelected(true));

    // Deliberately block fake verification; the GUI event loop and adapter
    // must remain responsive, and close/cancel cannot lose launch ownership.
    simulation_block_reads();
    assert(a.start("C:/test") && a.processTracked() && a.status() == "launching");
    assert(!a.start("C:/test") && !a.bindNativeParent(1));
    wait_for_read(); timer_wait(30);
    assert(a.status() == "launching" && a.processTracked());
    assert(a.setRect(30, 40, 300, 500));
    assert(!a.requestClose() && a.status() == "closing");
    assert(!a.setSelected(false));
    assert(a.cancelClose() && a.status() == "launching");
    // Restoring the active view is the owner's job after cancellation.
    assert(a.setSelected(true));
    simulation_release_reads(); wait_for_handoff(a);
    assert(a.status() == "discovering" && simulation_starts() == 1);
    assert(a.testProfile() == "C:\\Users\\Test User\\Temp\\Sa6i-Clean-HostTest-123-0");
    const QString firstProfile = a.testProfile();
    simulation_make_window(); timer_wait(240);
    assert(a.status() == "attached" && simulation_show() == SW_SHOWNA);
    assert(simulation_rect_left() == 30 && simulation_rect_bottom() == 500);
    assert(!a.requestClose() && a.status() == "closing" && simulation_close_messages() == 1);
    assert(!a.requestClose() && simulation_close_messages() == 1);
    assert(!a.setSelected(false));
    assert(a.cancelClose() && a.status() == "attached" && a.processTracked());
    // The adapter keeps polling after cancellation, even if no gate polls.
    simulation_exit(); timer_wait(240);
    assert(!a.processTracked() && a.status() == "idle");

    // Close during blocked launch: no approval until handoff and process exit.
    // Explicitly select before launching; requestClose must clear this even
    // when a caller does not issue a separate hide first.
    assert(a.setSelected(true));
    const int showRequestsBeforeClose = simulation_show_requests();
    simulation_block_reads(); assert(a.start("C:/test")); wait_for_read();
    assert(!a.requestClose() && a.status() == "closing" && a.processTracked());
    assert(!a.requestClose()); simulation_release_reads();
    // Close messages are counted on the GUI thread, only after handoff.
    for (int i = 0; i < 300 && simulation_close_messages() < 2; ++i) timer_wait(10);
    assert(simulation_close_messages() == 2 && simulation_starts() == 2 &&
           a.processTracked() && a.status() == "closing");
    assert(simulation_show_requests() == showRequestsBeforeClose && simulation_show() == SW_HIDE);
    assert(a.testProfile() != firstProfile && !a.testProfile().isEmpty());
    simulation_exit(); timer_wait(240);
    assert(!a.processTracked() && a.status() == "closed");
    assert(!a.start("C:/test")); // closed hosts require explicit rebind/reset
    assert(a.bindNativeParent(1) && a.status() == "idle");

    // A failed async launch also resolves a pending close without leaking or
    // claiming that scheduling meant launch success.
    simulation_fail_launch(); simulation_block_reads();
    assert(a.start("C:/test")); wait_for_read();
    assert(!a.requestClose()); simulation_release_reads();
    for (int i = 0; i < 300 && a.processTracked(); ++i) timer_wait(10);
    assert(!a.processTracked() && a.status() == "closed" && a.error() == 193);
    assert(!a.testProfile().isEmpty() && a.testProfile() != firstProfile);
    assert(a.requestClose());
    assert(changes >= 10);
    std::puts("Qt adapter + fake-Win32 backend tests passed");
}
