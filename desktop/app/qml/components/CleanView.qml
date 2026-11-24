// SPDX-License-Identifier: GPL-3.0-or-later
// View used only by the guarded Sa6i Clean experiment.
import QtQuick

Item {
    id: root
    // The owner controls visibility and supplies the app's single title bar.
    // The native host must map this viewport to its HWND; a QQuickItem is not
    // itself a native window.
    property bool active: false
    property bool embedded: false
    // Supplied by the owner; receives wheel notches for the embedded window.
    property var backend: null
    property string statusMessage: qsTr("Sa6i Clean is not connected.")
    readonly property alias viewport: viewport

    visible: active
    clip: true
    implicitWidth: 880
    implicitHeight: 600

    Rectangle {
        anchors.fill: parent
        color: "#101720"
    }
    Item {
        id: viewport
        objectName: "cleanNativeViewport"
        anchors.fill: parent
        clip: true

        // The cleaner runs in another process and does not hold keyboard focus,
        // so Windows delivers the wheel here. Relay it to the embedded window in
        // physical screen pixels; unforwarded events fall through to the host.
        WheelHandler {
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            acceptedModifiers: Qt.NoModifier
            enabled: root.active && root.embedded && !!root.backend
            onWheel: (event) => {
                if (!root.backend || event.angleDelta.y === 0) return
                const point = viewport.mapToGlobal(event.x, event.y)
                const win = viewport.Window.window
                const dpr = win && win.screen ? win.screen.devicePixelRatio : 1
                if (root.backend.forwardWheel(Math.round(point.x * dpr), Math.round(point.y * dpr),
                                              event.angleDelta.y)) {
                    event.accepted = true
                    return
                }
                // Not attached (or closing): fall back to scrolling the host page.
                event.accepted = false
            }
        }

        // Never display a fake cleaner UI when no native window is attached.
        Text {
            objectName: "cleanHostStatus"
            anchors.centerIn: parent
            width: Math.max(0, parent.width - 48)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            visible: !root.embedded
            text: root.statusMessage
            color: "#c9d6df"
            font.pixelSize: 15
        }
    }
}
