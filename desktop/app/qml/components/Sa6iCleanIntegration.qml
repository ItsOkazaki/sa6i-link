// SPDX-License-Identifier: GPL-3.0-or-later
// Experimental integration. Only enabled by a special Windows build AND an
// explicit --sa6i-clean-test-dir=<absolute path> argument. Not a release UI.
import QtQuick
import QtQuick.Window

Item {
    id: root
    required property var hostWindow
    property real titleBarHeight: 48
    property real captionButtonsWidth: 138
    property color headerColor: "#192430"
    property color headerTextColor: "white"
    property bool cleanOpen: false
    property bool shuttingDown: false
    // Native child windows do not obey QML z-order. The owner must report
    // visible overlays so both the child and cleaner layout can be hidden.
    property bool externalOverlayOpen: false
    property string initializationError: ""
    property bool viewportReady: false
    // A failed async visibility request means we cannot assume the native
    // child is hidden, even though the QML layout is no longer visible.
    property bool hideRequestFailed: false
    property bool hideAttemptActive: false
    readonly property var backend: hostWindow.sa6iCleanBackend
    property string testDirectory: {
        const prefix = "--sa6i-clean-test-dir="
        for (const argument of Qt.application.arguments)
            if (argument.indexOf(prefix) === 0) return argument.substring(prefix.length)
        return ""
    }
    readonly property bool available: !!backend && testDirectory.length > 0
    readonly property bool closePending: closeGate.pending
    signal closeApproved(string action)

    function requestHide() {
        if (hideAttemptActive) return false
        hideAttemptActive = true
        try {
            const ok = hostWindow.sa6iSyncCleanViewport(null, false)
            if (!ok && !hideRequestFailed)
                console.warn("Sa6i Clean: could not queue hiding the native cleaner window")
            hideRequestFailed = !ok
            return ok
        } finally {
            hideAttemptActive = false
        }
    }
    function syncViewport() {
        if (!backend || !backend.initialized || backend.status === "closed") {
            viewportReady = false
            hideRequestFailed = false
            return
        }
        const showing = cleanOpen && !externalOverlayOpen && !closeGate.pending && !shuttingDown && root.visible
        if (showing) {
            viewportReady = hostWindow.sa6iSyncCleanViewport(cleanView.viewport, true)
            if (viewportReady) hideRequestFailed = false
        } else {
            viewportReady = false
            // The close path has already requested hiding; the adapter rejects
            // new selection changes while closing, so do not report that as a
            // new hide failure or clear an earlier one.
            if (backend.status !== "closing") requestHide()
        }
    }
    function openClean() {
        if (!available || externalOverlayOpen || shuttingDown || closeGate.pending) return
        initializationError = ""
        if (!backend.initialized || backend.status === "closed") {
            if (!hostWindow.sa6iBindCleanParent()) {
                initializationError = qsTr("Could not initialize the experimental cleaner host.")
                cleanOpen = true
                return
            }
        }
        cleanOpen = true
        syncViewport()
        if (!backend.processTracked && backend.status === "idle")
            backend.start(testDirectory)
    }
    // A later activation cancels a pending tray action, but never cancels an
    // explicit quit. A WM_CLOSE already posted to the child may still finish.
    function cancelTrayCloseForReactivation() {
        if (!closeGate.pending || closeGate.pendingAction !== "tray") return false
        return closeGate.keepOpen()
    }
    // Tray teardown was approved but a newer activation kept this same
    // window alive. Only reset after the cleaner has actually exited; return
    // to Sa6i Link so the closed host can be explicitly rebound on next open.
    function resumeAfterTrayReactivation() {
        if (!shuttingDown || closeGate.pending || !backend || backend.processTracked) return false
        cleanOpen = false
        shuttingDown = false
        return true
    }
    // Returns false only if no cleaner backend exists. A missing/broken gate
    // must not be treated as permission to destroy a tracked process.
    function requestClose(action) {
        if (!backend) return false
        if (closeGate.pending || shuttingDown) return true
        // Hide the native child before showing any QML close UI.
        if (backend.initialized && backend.status !== "closing" && backend.status !== "closed") requestHide()
        if (!closeGate.request(action))
            console.warn("Sa6i Clean close gate rejected an action; keeping the window open")
        return true
    }

    CleanCloseGate {
        id: closeGate
        backend: root.backend
        onCloseApproved: (action) => { root.shuttingDown = true; root.closeApproved(action) }
        onCloseCancelled: { root.shuttingDown = false; root.syncViewport() }
        onGateError: (message) => console.warn(message)
    }
    Timer {
        interval: 100
        repeat: true
        running: root.available && root.backend && root.backend.initialized && !root.shuttingDown
        onTriggered: root.syncViewport()
    }
    onCleanOpenChanged: syncViewport()
    onExternalOverlayOpenChanged: syncViewport()
    onVisibleChanged: syncViewport()

    CleanEntry {
        id: entry
        objectName: "sa6iCleanEntry"
        anchors.right: parent.right
        anchors.rightMargin: 160
        y: Math.max(0, (root.titleBarHeight - height) / 2)
        width: 112
        height: 36
        visible: root.available && !root.cleanOpen && !root.externalOverlayOpen && !closeGate.pending && !root.shuttingDown
        available: visible
        onOpenRequested: root.openClean()
        Component.onCompleted: root.hostWindow.addCaptionHole(entry)
        Component.onDestruction: root.hostWindow.removeCaptionHole(entry)
    }

    // Replace the app's existing title content while retaining its native
    // caption buttons at the right. The cleaner does not own another window
    // toolbar in the Qt layout.
    Rectangle {
        id: cleanHeader
        objectName: "cleanIntegratedHeader"
        anchors.top: parent.top
        anchors.left: parent.left
        width: Math.max(0, parent.width - root.captionButtonsWidth)
        height: root.titleBarHeight
        visible: root.cleanOpen && !root.externalOverlayOpen
        color: root.headerColor

        Rectangle {
            id: backButton
            objectName: "cleanBackButton"
            anchors.left: parent.left
            anchors.leftMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            width: backText.implicitWidth + 24
            height: Math.min(36, parent.height)
            radius: 8
            color: backMouse.pressed ? Qt.rgba(0.5, 0.5, 0.5, 0.24)
                 : (backMouse.containsMouse ? Qt.rgba(0.5, 0.5, 0.5, 0.14) : "transparent")
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Back to Sa6i Link")
            Keys.onReturnPressed: root.cleanOpen = false
            Keys.onSpacePressed: root.cleanOpen = false
            Component.onCompleted: root.hostWindow.addCaptionHole(backButton)
            Component.onDestruction: root.hostWindow.removeCaptionHole(backButton)
            Text {
                id: backText
                anchors.centerIn: parent
                text: qsTr("Back to Sa6i Link")
                color: root.headerTextColor
                font.pixelSize: 14
            }
            MouseArea {
                id: backMouse
                anchors.fill: parent
                hoverEnabled: true
                onClicked: root.cleanOpen = false
            }
        }
        Text {
            anchors.left: backButton.right
            anchors.leftMargin: 20
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("Sa6i Clean")
            color: root.headerTextColor
            font.pixelSize: 18
            font.bold: true
        }
    }

    CleanView {
        id: cleanView
        anchors.top: parent.top
        anchors.topMargin: root.titleBarHeight
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        active: root.cleanOpen && !root.externalOverlayOpen
        embedded: !!root.backend && root.backend.status === "attached" && root.viewportReady
        statusMessage: {
            if (root.initializationError.length) return root.initializationError
            if (!root.backend) return qsTr("Sa6i Clean is not connected.")
            switch (root.backend.status) {
            case "launching": return qsTr("Checking and starting Sa6i Clean…")
            case "discovering": return qsTr("Waiting for the cleaner window…")
            case "unattached": return qsTr("The cleaner window could not be attached. Close the cleaner before trying again.")
            case "closing": return qsTr("Waiting for the cleaner to close…")
            case "attached": return qsTr("Could not position the cleaner safely in this window.")
            case "idle": return root.backend.error ? qsTr("Cleaner launch failed (error %1).").arg(root.backend.error) : qsTr("Cleaner is not running.")
            default: return qsTr("Cleaner status: %1").arg(root.backend.status)
            }
        }
    }

    // The native child was requested hidden before this panel is shown.
    Rectangle {
        objectName: "sa6iCleanClosePrompt"
        z: 5
        visible: closeGate.pending
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.titleBarHeight + 12
        width: Math.min(480, parent.width - 24)
        height: 134
        radius: 10
        color: "#192430"
        Text {
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top; anchors.margins: 14
            wrapMode: Text.Wrap
            color: "white"
            text: qsTr("Waiting for Sa6i Clean to close. If it does not close, close it yourself or keep Sa6i Link open. A close request already sent may still finish.")
        }
        Rectangle {
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 12
            width: 160; height: 36; radius: 7; color: "#425d71"
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Keep Sa6i Link open")
            Keys.onReturnPressed: closeGate.keepOpen()
            Keys.onSpacePressed: closeGate.keepOpen()
            Text { anchors.centerIn: parent; color: "white"; text: qsTr("Keep open") }
            MouseArea { anchors.fill: parent; onClicked: closeGate.keepOpen() }
        }
    }
}
