// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick

// Stands in for the Rust Preferences in QML tests: Bloom, light.
QtObject {
    property string theme: "bloom"
    property string colorMode: "light"
    property bool amoled: false
    property bool combMotion: false
    property string seed: ""
    property string commandPaletteHotkey: ""
    property bool streamPcAudioToPhone: false
    property bool island: true
    property bool islandCalls: true
    property bool islandMedia: true
    property bool islandNotifications: true
    property bool islandTransfers: true
}
