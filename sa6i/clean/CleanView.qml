// SPDX-License-Identifier: GPL-3.0-or-later
// Standalone QML view for a future native cleaner host. Not wired into Sa6i Link.
import QtQuick

Item {
    id: root

    // The owner controls when this view is visible and manages the process.
    // The native host must map viewport coordinates and visibility to its HWND;
    // a QQuickItem is not itself a native window.
    property bool active: false
    property bool embedded: false
    property string statusMessage: qsTr("Sa6i Clean is not connected.")
    readonly property alias viewport: viewport
    signal backRequested()

    visible: active
    clip: true
    implicitWidth: 880
    implicitHeight: 600

    Rectangle {
        anchors.fill: parent
        color: "#101720"
    }

    Rectangle {
        id: toolbar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 56
        color: "#192430"

        Rectangle {
            id: backButton
            objectName: "cleanBackButton"
            anchors.left: parent.left
            anchors.leftMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            width: backText.implicitWidth + 24
            height: 36
            radius: 8
            color: backMouse.pressed ? "#425d71" : "#2a4050"
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Back to Sa6i Link")
            Keys.onReturnPressed: root.backRequested()
            Keys.onSpacePressed: root.backRequested()
            Text {
                id: backText
                anchors.centerIn: parent
                text: qsTr("Back to Sa6i Link")
                color: "white"
                font.pixelSize: 14
            }
            MouseArea {
                id: backMouse
                anchors.fill: parent
                onClicked: root.backRequested()
            }
        }

        Text {
            anchors.left: backButton.right
            anchors.leftMargin: 20
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("Sa6i Clean")
            color: "white"
            font.pixelSize: 18
            font.bold: true
        }
    }

    Item {
        id: viewport
        objectName: "cleanNativeViewport"
        anchors.top: toolbar.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        clip: true

        // No fake cleaner UI: show an explicit status until a host reports an
        // attached window. The host must also hide its HWND when inactive.
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
