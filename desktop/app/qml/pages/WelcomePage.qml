// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import sa6i.link

// First run: pair a phone. Also covers the moment before the core is ready
// and the (rare) case where it failed to start.
Item {
    id: page

    readonly property string status: AppController.status

    Column {
        anchors.centerIn: parent
        width: Math.min(460, parent.width - 48)
        spacing: 22

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 52; height: 52
            radius: Theme.radiusMd
            color: "black"
            Image {
                anchors.fill: parent
                anchors.margins: 2
                fillMode: Image.PreserveAspectFit
                source: "qrc:/branding/sa6i-link.png"
            }
        }
        Column {
            width: parent.width
            spacing: 6
            Txt {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: qsTr("Welcome to Sa6i Hub")
                role: "displaySmall"
            }
            Txt {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                role: "body"
                muted: true
                text: page.status === "failed"
                      ? qsTr("Sa6i Link couldn't start.")
                      : qsTr("Use Sa6i Link to connect your phone and this PC. Pair once and they can find each other again.")
            }
        }

        Card {
            width: parent.width
            padding: 24
            visible: page.status === "ready"
            PairingPanel {
                width: parent.width
                cancellable: false
                running: page.visible && page.status === "ready"
            }
        }

        Spinner {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: page.status === "starting"
            width: 28; height: 28
        }

        Column {
            width: parent.width
            spacing: 12
            visible: page.status === "failed"
            Txt {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                role: "code"
                size: 12
                muted: true
                text: AppController.error
            }
            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                variant: "tonal"
                iconPath: Icons.folder
                text: qsTr("Open the logs folder")
                onClicked: Qt.openUrlExternally(AppController.logsUrl())
            }
        }
    }
}
