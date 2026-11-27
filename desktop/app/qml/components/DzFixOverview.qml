// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import sa6i.link

// Preview: displays only supplied evidence. Does not collect or change anything.
Rectangle {
    id: root
    color: "#0c101c"
    property bool busy: false
    property string payload: ""
    signal backRequested()
    signal scanRequested()
    readonly property var snapshot: {
        if (!payload) return null
        try { return JSON.parse(payload) } catch (e) { return { error: "Invalid scan result." } }
    }
    function available(v) { return v && v.state === "available" }
    function gib(n) { return (n / 1073741824).toFixed(1) + " GiB" }
    function cpuValue() { return available(snapshot && snapshot.cpu_percent) ? snapshot.cpu_percent.value.toFixed(1) + "%" : "—" }
    function memoryValue() { return available(snapshot && snapshot.memory) ? gib(snapshot.memory.value.available) : "—" }
    function driveValue() { return available(snapshot && snapshot.windows_drive) ? gib(snapshot.windows_drive.value.available_to_user) : "—" }
    function networkValue() { return available(snapshot && snapshot.network_connected) ? (snapshot.network_connected.value ? "Connected" : "Not connected") : "—" }
    function missing() { return payload ? "Unavailable" : "Not measured" }

    component MetricCard: Rectangle {
        id: metric
        property string title
        property string value
        property string detail
        property string accent: "#9d8aff"
        radius: 12
        color: "#151b2c"
        border.color: "#29324a"
        implicitHeight: 145
        Column {
            anchors.fill: parent; anchors.margins: 18; spacing: 9
            Text { width: parent.width; color: "#aab5cd"; font.pixelSize: 13; text: metric.title; elide: Text.ElideRight }
            Text { width: parent.width; color: metric.accent; font.pixelSize: 25; font.bold: true; text: metric.value; elide: Text.ElideRight }
            Text { width: parent.width; color: "#b5bfd2"; font.pixelSize: 12; text: metric.detail; wrapMode: Text.WordWrap }
        }
    }

    Flickable {
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: contents.height + 48
        Column {
            id: contents
            x: 24
            width: Math.max(0, parent.width - 48)
            y: 20
            spacing: 20
            Row {
                spacing: 14
                Button { objectName: "dzFixBack"; text: qsTr("Back to Hub"); variant: "tonal"; onClicked: root.backRequested() }
                Text { anchors.verticalCenter: parent.verticalCenter; text: "DZ FIX"; font.pixelSize: 17; font.bold: true; color: "#f2f4ff" }
            }
            Column {
                width: parent.width; spacing: 5
                Text { text: qsTr("System overview"); color: "#f2f4ff"; font.pixelSize: 28; font.bold: true }
                Text { width: parent.width; wrapMode: Text.WordWrap; text: qsTr("Read-only evidence from your PC. No repairs, internet requests or background monitoring."); color: "#aab5cd"; font.pixelSize: 13 }
            }
            Row {
                spacing: 12
                Button {
                    objectName: "dzFixScan"
                    text: root.busy ? qsTr("Sampling CPU…") : qsTr("Run 10-second local scan")
                    enabled: !root.busy
                    onClicked: root.scanRequested()
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#aab5cd"; font.pixelSize: 12
                    text: root.busy ? qsTr("Please wait") : (root.snapshot && !root.snapshot.error && root.snapshot.captured_unix_ms > 0 ? qsTr("Captured: ") + new Date(root.snapshot.captured_unix_ms).toLocaleString() : qsTr("Not scanned"))
                }
            }
            Text {
                objectName: "dzFixError"
                visible: !!root.snapshot && !!root.snapshot.error
                width: parent.width; wrapMode: Text.WordWrap
                color: "#ffb6b6"; font.pixelSize: 13
                text: root.snapshot && root.snapshot.error ? root.snapshot.error : ""
            }
            Grid {
                id: cards
                width: parent.width
                columns: width >= 650 ? 2 : 1
                spacing: 12
                readonly property real cardWidth: columns === 2 ? (width - spacing) / 2 : width
                MetricCard {
                    objectName: "dzCpuCard"; width: cards.cardWidth; title: qsTr("PROCESSOR")
                    value: root.cpuValue()
                    detail: root.available(root.snapshot && root.snapshot.cpu_percent) ? qsTr("Average during scan · processor group reported by Windows") : root.missing()
                }
                MetricCard {
                    objectName: "dzMemoryCard"; width: cards.cardWidth; title: qsTr("MEMORY AVAILABLE"); accent: "#64dbef"
                    value: root.memoryValue()
                    detail: root.available(root.snapshot && root.snapshot.memory) ? qsTr("of ") + root.gib(root.snapshot.memory.value.total) + qsTr(" physical memory") : root.missing()
                }
                MetricCard {
                    objectName: "dzDriveCard"; width: cards.cardWidth; title: qsTr("WINDOWS DRIVE AVAILABLE"); accent: "#64dbef"
                    value: root.driveValue()
                    detail: root.available(root.snapshot && root.snapshot.windows_drive) ? qsTr("of ") + root.gib(root.snapshot.windows_drive.value.total) + qsTr(" available to this user") : root.missing()
                }
                MetricCard {
                    objectName: "dzNetworkCard"; width: cards.cardWidth; title: qsTr("NETWORK")
                    value: root.networkValue()
                    detail: root.available(root.snapshot && root.snapshot.network_connected) ? qsTr("Windows network status; internet access not tested.") : root.missing()
                }
            }
            Rectangle {
                width: parent.width; height: notes.height + 32; radius: 12; color: "#151b2c"; border.color: "#29324a"
                Column {
                    id: notes; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16; spacing: 8
                    Text { color: "#f2f4ff"; font.pixelSize: 16; font.bold: true; text: qsTr("What this scan can tell you") }
                    Text { width: parent.width; wrapMode: Text.WordWrap; color: "#b5bfd2"; font.pixelSize: 13; text: qsTr("These are measurements, not a diagnosis. CPU averages cover the Windows-reported processor group; memory and disk are snapshots. Network connection does not prove internet access.") }
                    Text { width: parent.width; wrapMode: Text.WordWrap; color: "#aab5cd"; font.pixelSize: 12; text: qsTr("Temperature, GPU health, internet tests and repair actions are not included yet.") }
                }
            }
        }
    }
}
