// SPDX-License-Identifier: GPL-3.0-or-later
// A close coordinator wired to a C++ QtEmbedAdapter with fake Win32 functions.
import QtQml
import ".."

QtObject {
    id: root
    property var adapter: null
    property QtObject gate: CloseGate { backend: root.adapter; pollInterval: 100000 }
    function launch() {
        return adapter.setRect(10, 20, 300, 400) && adapter.setSelected(true) && adapter.start("C:/test")
    }
    function adapterPoll() { adapter.poll() }
}
