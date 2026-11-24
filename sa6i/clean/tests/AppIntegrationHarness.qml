// SPDX-License-Identifier: GPL-3.0-or-later
// Uses the actual app integration QML with a simulated parent window.
import QtQuick
import QtQuick.Window
import "../../../desktop/app/qml/components"

Window {
    id: window
    width: 800; height: 600
    visible: true
    property var sa6iCleanBackend: null
    property var bindBackendHook: null
    property var integrationObject: integration
    property bool simulatedOverlayOpen: false
    property int overlayClicks: 0
    property int savedCount: 0
    property int teardownCount: 0
    signal sa6iCloseApproved(string action)
    function requestSa6iClose(action) { return integration.requestClose(action) }
    function resumeSa6iAfterTrayReactivation() { return integration.resumeAfterTrayReactivation() }
    function cancelSa6iTrayCloseForReactivation() { return integration.cancelTrayCloseForReactivation() }
    function bringToFront() {}
    function saveWindowState() { savedCount++ }
    function releaseAndTeardown() {
        if (sa6iCleanBackend && sa6iCleanBackend.processTracked) return false
        teardownCount++
        return true
    }
    Rectangle {
        anchors.fill: parent
        z: 100
        color: "#334455"
        visible: window.simulatedOverlayOpen
        MouseArea { anchors.fill: parent; onClicked: window.overlayClicks++ }
    }
    function addCaptionHole(item) {}
    function removeCaptionHole(item) {}
    function sa6iBindCleanParent() {
        if (!sa6iCleanBackend.initialized || sa6iCleanBackend.status === "closed")
            return !!bindBackendHook && bindBackendHook.bind()
        return true
    }
    function sa6iSyncCleanViewport(item, selected) {
        if (!sa6iCleanBackend.initialized) return false
        if (!selected || !item) return sa6iCleanBackend.setSelected(false)
        return sa6iCleanBackend.setRect(0, 48, 800, 600) && sa6iCleanBackend.setSelected(true)
    }
    Sa6iCleanIntegration {
        id: integration
        anchors.fill: parent
        z: 1100
        hostWindow: window
        externalOverlayOpen: window.simulatedOverlayOpen
        titleBarHeight: 48
        testDirectory: "C:/test"
        onCloseApproved: (action) => window.sa6iCloseApproved(action)
    }
}
