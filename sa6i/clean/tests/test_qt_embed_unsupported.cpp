// SPDX-License-Identifier: GPL-3.0-or-later
// Non-Windows stub must never report a launch or a tracked process.
#include "../qt_embed_adapter.h"
#include <QtCore/QCoreApplication>
#include <cassert>
#include <cstdio>
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    QtEmbedAdapter a;
    assert(!a.supported() && !a.initialized() && !a.processTracked());
    assert(a.status() == "unsupported" && a.error() == 0 && a.testProfile().isEmpty());
    assert(!a.bindNativeParent(1) && !a.start("C:/test"));
    assert(!a.setRect(0, 0, 1, 1) && !a.setSelected(true));
    assert(a.requestClose() && !a.cancelClose());
    a.poll();
    std::puts("Qt adapter unsupported-platform tests passed");
}
