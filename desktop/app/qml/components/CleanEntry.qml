// SPDX-License-Identifier: GPL-3.0-or-later
// Navigation entry used only by the guarded Sa6i Clean experiment.
import QtQuick

Rectangle {
    id: root
    signal openRequested()
    property bool available: true
    implicitWidth: entryText.implicitWidth + 32
    implicitHeight: 36
    radius: 8
    color: !available ? "#39414a" : (area.pressed ? "#425d71" : "#2a4050")
    opacity: available ? 1 : 0.6
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("Open Sa6i Clean")
    enabled: available
    Keys.onReturnPressed: if (root.available) root.openRequested()
    Keys.onSpacePressed: if (root.available) root.openRequested()

    Text {
        id: entryText
        anchors.centerIn: parent
        text: qsTr("Sa6i Clean")
        color: "white"
        font.pixelSize: 14
    }
    MouseArea {
        id: area
        anchors.fill: parent
        enabled: root.available
        onClicked: root.openRequested()
    }
}
