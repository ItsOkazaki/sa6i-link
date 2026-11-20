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
