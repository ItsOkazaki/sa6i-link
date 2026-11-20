// SPDX-License-Identifier: GPL-3.0-or-later
// Fake backend for offscreen tests. No native process or Win32 calls.
import QtQml
import ".."

QtObject {
    id: root
    property QtObject backend: QtObject {
        property bool alive: true
        property bool closing: false
        property bool cancelFails: false
        property bool waitFails: false
        property bool throwOnPoll: false
        property bool nonBooleanResult: false
        property bool reenterKeepOpen: false
        property int requests: 0
        property int polls: 0
        property int cancellations: 0
        function poll() {
            polls++
            if (throwOnPoll) throw new Error("poll failed")
        }
        function requestClose() {
            requests++
            if (reenterKeepOpen) root.gate.keepOpen()
            if (nonBooleanResult) return 1
            if (waitFails) return false
            if (!alive) return true
            closing = true
            return false
        }
        function cancelClose() {
            cancellations++
            if (cancelFails || waitFails || !alive || !closing) return false
            closing = false
            return true
        }
    }
    property QtObject gate: CloseGate {
        backend: root.backend
        pollInterval: 100000
    }
}
