// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import sa6i.link

// Monitor: this PC, measured once a second.
//
// Every number and every sentence here arrives finished from
// `sa6i_link_intel::view` — the page places tiles, bars and lines, and formats
// nothing. A tile with no reading shows a dash and the reason for it; a
// sparkline draws a gap where a sample is missing.
Item {
    id: page
    // Set by the window's Loader; the page needs no data from it, but every
    // page carries it so the loader's line runs unchanged.
    property bool active: false

    readonly property var frame: {
        if (IntelHost.frame.length === 0)
            return null
        try { return JSON.parse(IntelHost.frame) } catch (e) { return null }
    }
    readonly property var tiles: frame && frame.tiles ? frame.tiles : []
    readonly property var cores: frame && frame.cores ? frame.cores : []
    readonly property var processes: frame && frame.processes ? frame.processes : []
    readonly property var volumes: frame && frame.volumes ? frame.volumes : []
    readonly property var cpuPoints: frame && frame.cpu ? frame.cpu : []
    readonly property var memoryPoints: frame && frame.memory ? frame.memory : []
    readonly property string summary: frame && frame.summary ? frame.summary : ""
    readonly property string liveText: IntelHost.live
        ? qsTr("Every %1 s · %2 samples").arg(IntelHost.intervalMs / 1000).arg(IntelHost.samples)
        : qsTr("Paused")

    /// Whether the frame carried a value at all. `null` is a measurement that
    /// did not happen, and it never becomes zero.
    function has(value) {
        return value !== null && value !== undefined
    }
    function clamp01(value) {
        return Math.max(0, Math.min(1, value))
    }

    Component.onCompleted: IntelHost.start()
    Component.onDestruction: IntelHost.stop()

    Flickable {
        anchors.fill: parent
        contentWidth: width
        contentHeight: content.height + Theme.contentPadding
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: content
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: Theme.contentPadding
            anchors.rightMargin: Theme.contentPadding
            anchors.topMargin: 8
            spacing: 12

            // ---- What the rules make of what is on screen ----
            Row {
                width: parent.width
                height: 28
                spacing: 10

                Txt {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - liveChip.width - parent.spacing
                    text: page.summary
                    role: "title"
                }
                Rectangle {
                    id: liveChip
                    anchors.verticalCenter: parent.verticalCenter
                    width: liveRow.width + 20
                    height: 26
                    radius: Theme.graphite ? Theme.radiusSm : height / 2
                    color: Theme.surfaceContainerHighest
                    Row {
                        id: liveRow
                        anchors.centerIn: parent
                        spacing: 6
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 7; height: 7; radius: 4
                            color: IntelHost.live ? Theme.primary : Theme.surfaceContentVariant
                            opacity: IntelHost.live ? 1.0 : 0.5
                        }
                        Txt {
                            text: page.liveText
                            role: "caption"
                            muted: true
                        }
                    }
                }
            }

            // Nothing measured yet: say which second we are waiting for rather
            // than showing four zeroes.
            Card {
                width: parent.width
                height: 88
                visible: page.frame === null
                Column {
                    width: parent.width
                    spacing: 4
                    Txt { text: qsTr("Measuring this PC"); role: "title" }
                    Txt {
                        width: parent.width
                        text: qsTr("The first sample cannot know a rate. "
                                   + "The page fills as soon as the second one arrives.")
                        role: "bodySmall"
                        muted: true
                    }
                }
            }

            // ---- The four numbers ----
            Grid {
                id: tileGrid
                width: parent.width
                columns: width >= 860 ? 4 : (width >= 440 ? 2 : 1)
                spacing: 12

                Repeater {
                    model: page.tiles
                    delegate: Card {
                        width: (tileGrid.width - tileGrid.spacing * (tileGrid.columns - 1)) / tileGrid.columns
                        height: 122
                        readonly property real fill: page.has(modelData.fraction)
                            ? page.clamp01(modelData.fraction) : 0
                        Column {
                            width: parent.width
                            spacing: 4
                            Txt { text: modelData.label; role: "label"; muted: true }
                            Txt {
                                text: modelData.value
                                role: "headline"
                                muted: page.has(modelData.missing)
                            }
                            Txt {
                                width: parent.width
                                text: modelData.note
                                role: "caption"
                                muted: true
                            }
                            Item { width: 1; height: 4 }
                            // The track is always drawn; the fill only appears
                            // when there is a real share to show.
                            Rectangle {
                                width: parent.width
                                height: 4
                                radius: 2
                                color: Theme.surfaceContainerHighest
                                Rectangle {
                                    width: parent.width * fill
                                    height: parent.height
                                    radius: parent.radius
                                    color: Theme.primary
                                    Behavior on width {
                                        enabled: !Theme.reduceMotion
                                        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ---- The last minute ----
            Row {
                width: parent.width
                spacing: 12

                Repeater {
                    model: [
                        { label: qsTr("CPU"), points: page.cpuPoints },
                        { label: qsTr("Memory"), points: page.memoryPoints }
                    ]
                    delegate: Card {
                        width: (parent.width - parent.spacing) / 2
                        height: 116
                        Column {
                            width: parent.width
                            spacing: 8
                            Item {
                                width: parent.width
                                height: 16
                                Txt {
                                    anchors.left: parent.left
                                    text: modelData.label
                                    role: "label"
                                    muted: true
                                }
                                Txt {
                                    anchors.right: parent.right
                                    text: qsTr("last minute")
                                    role: "caption"
                                    muted: true
                                }
                            }
                            Sparkline {
                                width: parent.width
                                height: 56
                                points: modelData.points
                            }
                        }
                    }
                }
            }

            // ---- Cores ----
            Card {
                width: parent.width
                height: coresColumn.height + 32
                Column {
                    id: coresColumn
                    width: parent.width
                    spacing: 10
                    Txt { text: qsTr("Logical processors"); role: "label"; muted: true }
                    Grid {
                        id: coreGrid
                        width: parent.width
                        columns: Math.max(1, Math.floor(width / 62))
                        spacing: 8
                        Repeater {
                            model: page.cores
                            delegate: Item {
                                width: 54
                                height: 46
                                readonly property real fill: page.has(modelData.percent)
                                    ? page.clamp01(modelData.percent / 100) : 0
                                readonly property string percentText: page.has(modelData.percent)
                                    ? Math.round(modelData.percent) + " %" : "—"
                                Rectangle {
                                    id: coreBar
                                    anchors.bottom: parent.bottom
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: 20
                                    height: 30
                                    radius: 4
                                    color: Theme.surfaceContainerHighest
                                    Rectangle {
                                        anchors.bottom: parent.bottom
                                        width: parent.width
                                        // A core that was not measured is an
                                        // empty bar, never a short one.
                                        height: parent.height * fill
                                        radius: parent.radius
                                        color: Theme.primary
                                    }
                                }
                                Txt {
                                    anchors.top: parent.top
                                    width: parent.width
                                    horizontalAlignment: Text.AlignHCenter
                                    text: percentText
                                    role: "caption"
                                    muted: !page.has(modelData.percent)
                                }
                            }
                        }
                    }
                }
            }

            // ---- Volumes ----
            Card {
                width: parent.width
                height: volumesColumn.height + 32
                Column {
                    id: volumesColumn
                    width: parent.width
                    spacing: 2
                    Txt { text: qsTr("Volumes"); role: "label"; muted: true }
                    Repeater {
                        model: page.volumes
                        delegate: Item {
                            width: volumesColumn.width
                            height: 32
                            readonly property real fill: page.has(modelData.usedPercent)
                                ? page.clamp01(modelData.usedPercent / 100) : 0
                            Txt {
                                id: volumeMount
                                anchors.verticalCenter: parent.verticalCenter
                                width: 48
                                text: modelData.mount
                                role: "body"
                            }
                            Txt {
                                anchors.left: volumeMount.right
                                anchors.verticalCenter: parent.verticalCenter
                                width: 74
                                text: modelData.kind
                                role: "caption"
                                muted: true
                            }
                            Rectangle {
                                id: volumeTrack
                                anchors.left: volumeMount.right
                                anchors.leftMargin: 82
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 82 - 132
                                height: 6
                                radius: 3
                                color: Theme.surfaceContainerHighest
                                visible: width > 40
                                Rectangle {
                                    width: parent.width * fill
                                    height: parent.height
                                    radius: parent.radius
                                    color: Theme.primary
                                }
                            }
                            Txt {
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                width: 128
                                horizontalAlignment: Text.AlignRight
                                text: modelData.detail
                                role: "caption"
                                muted: true
                            }
                        }
                    }
                }
            }

            // ---- The heaviest processes ----
            Card {
                width: parent.width
                height: processesColumn.height + 32
                Column {
                    id: processesColumn
                    width: parent.width
                    spacing: 2
                    Txt { text: qsTr("Heaviest processes"); role: "label"; muted: true }
                    Repeater {
                        model: page.processes
                        delegate: Item {
                            width: processesColumn.width
                            height: 30
                            readonly property string shareText: page.has(modelData.share)
                                ? modelData.share.toFixed(1) + " %" : ""
                            Txt {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 240
                                text: modelData.name
                                role: "body"
                            }
                            Txt {
                                anchors.right: shareLabel.left
                                anchors.rightMargin: 16
                                anchors.verticalCenter: parent.verticalCenter
                                width: 96
                                horizontalAlignment: Text.AlignRight
                                text: modelData.memory
                                role: "body"
                                muted: !modelData.known
                            }
                            Txt {
                                id: shareLabel
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                width: 96
                                horizontalAlignment: Text.AlignRight
                                text: shareText
                                role: "caption"
                                muted: true
                            }
                        }
                    }
                }
            }

        }
    }
}
