// SPDX-License-Identifier: GPL-3.0-or-later
// Experimental coordinator only. Not connected to Sa6i Link.
import QtQml

QtObject {
    id: gate

    // Contract for a future adapter: poll() observes process exit without
    // blocking; requestClose() is idempotent and returns true ONLY after the
    // tracked process is confirmed gone and any launch has resolved;
    // cancelClose() returns true ONLY if the pending close was cancelled while
    // the adapter still owns any process or unresolved launch. The owner must
    // keep this object, the adapter and the parent HWND alive while pending,
    // and must intercept native close before it is accepted.
    property var backend: null
    property int pollInterval: 100
    readonly property bool pending: state.action !== ""
    readonly property string pendingAction: state.action
    property QtObject internalState: QtObject {
        id: state
        property string action: ""
        property bool cancelWanted: false
        property bool advancing: false
        property var closingBackend: null
    }
    signal closeApproved(string action)
    signal closeCancelled()
    signal gateError(string message)

    property Timer pollTimer: Timer {
        interval: Math.max(1, gate.pollInterval)
        repeat: true
        running: gate.pending
        onTriggered: gate.advance()
    }

    // A duplicate request cannot replace an existing tray/quit decision.
    function request(action) {
        if (pending || (action !== "tray" && action !== "quit") || !backend)
            return false
        state.closingBackend = backend
        state.action = action
        state.cancelWanted = false
        advance()
        return true
    }

    function keepOpen() {
        if (!pending) return false
        // Intent is sticky even if the backend's current wait fails or the
        // cleaner exits at the same instant. Never approve the old action.
        state.cancelWanted = true
        advance()
        return true
    }

    function finish(approved) {
        const action = state.action
        state.action = ""
        state.cancelWanted = false
        state.closingBackend = null
        if (approved) closeApproved(action)
        else closeCancelled()
    }

    function advance() {
        if (!pending || state.advancing) return
        if (!state.closingBackend) {
            gateError(qsTr("Cleaner host is unavailable; Sa6i Link will remain open."))
            return
        }
        state.advancing = true
        try {
            state.closingBackend.poll()
            if (state.cancelWanted) {
                if (state.closingBackend.cancelClose() === true) {
                    finish(false)
                    return
                }
                // The process may already have exited as cancellation began.
                // Release the pending action but still honor Keep open.
                if (state.closingBackend.requestClose() === true)
                    finish(false)
            } else if (state.closingBackend.requestClose() === true) {
                // A reentrant Keep open may arrive from a backend callback.
                finish(!state.cancelWanted)
            }
        } catch (e) {
            // Exceptions and non-boolean returns do not grant teardown.
            gateError(qsTr("Could not verify cleaner shutdown; Sa6i Link will remain open."))
        } finally {
            state.advancing = false
        }
    }
}
