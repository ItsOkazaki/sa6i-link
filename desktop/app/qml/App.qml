// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQml
import QtQml.Models
import sa6i.link

// Application root. The main window exists only while it's open: closing it
// destroys it (freeing its GPU resources) and Sa6i Link keeps running in
// the tray. A tray click, a second launch or a ringing request reopens it.
QtObject {
    id: app

    readonly property var mainWindow: mainLoader.item
    readonly property Loader mainLoader: Loader {
        active: false
        source: "qrc:/qt/qml/sa6i/link/qml/MainWindow.qml"
        onLoaded: {
            item.closeRequested.connect(app.onMainClosed)
            item.sa6iCloseApproved.connect(app.finishMainClose)
            item.restoreAndBringToFront()
        }
    }
    readonly property Loader laserLoader: Loader {
        active: AppController.laserActive
        source: active ? "qrc:/qt/qml/sa6i/link/qml/LaserOverlay.qml" : ""
    }
    property var islandWindow: null
    readonly property Component islandWindowComponent: Component {
        IslandWindow {}
    }

    function syncIslandWindow() {
        if (Preferences.island) {
            if (!app.islandWindow) {
                const w = islandWindowComponent.createObject(app)
                if (w) {
                    app.islandWindow = w
                } else {
                    console.warn("IslandWindow createObject failed:", islandWindowComponent.errorString())
                }
            }
        } else {
            if (app.islandWindow) {
                app.islandWindow.destroy()
                app.islandWindow = null
            }
        }
    }

    property var shelfWindow: null
    readonly property Component shelfWindowComponent: Component {
        ShelfWindow {}
    }

    function syncShelfWindow() {
        if (AppController.shelfOpen) {
            trayTrimTimer.stop()
            if (!app.shelfWindow) {
                const w = shelfWindowComponent.createObject(app)
                if (w) {
                    app.shelfWindow = w
                } else {
                    console.warn("ShelfWindow createObject failed:", shelfWindowComponent.errorString())
                }
            }
        } else {
            if (app.shelfWindow) {
                app.shelfWindow.destroy()
                app.shelfWindow = null
            }
            if (!app.mainWindow && Object.keys(app.openMirrors).length === 0)
                trayTrimTimer.restart()
        }
    }

    // A window for each phone screen or app being mirrored. Keyed by
    // `mirrorKey`, so a window lives as long as its mirroring.
    property var openMirrors: ({})
    readonly property Component mirrorWindowComponent: Component {
        MirrorWindow {}
    }

    function syncMirrorWindows() {
        let keys = []
        try {
            keys = JSON.parse(Mirror.windows).map(w => w.key)
        } catch (e) {}
        const current = app.openMirrors
        for (const k of Object.keys(current)) {
            if (keys.indexOf(k) < 0) {
                if (current[k])
                    current[k].destroy()
                delete current[k]
            }
        }
        for (const key of keys) {
            if (!current[key]) {
                const w = mirrorWindowComponent.createObject(app, { mirrorKey: key })
                if (w) {
                    current[key] = w
                } else {
                    console.warn("MirrorWindow createObject failed:", mirrorWindowComponent.errorString())
                }
            }
        }
        if (!app.mainWindow && Object.keys(current).length === 0 && !AppController.shelfOpen)
            trayTrimTimer.restart()
    }
    readonly property bool startMinimized: Qt.application.arguments.indexOf("--minimized") >= 0
        || Qt.application.arguments.indexOf("--send-to") >= 0

    readonly property Timer trayTrimTimer: Timer {
        interval: 350
        onTriggered: {
            if (!app.mainWindow && Object.keys(app.openMirrors).length === 0 && !AppController.shelfOpen) {
                gc()
                AppController.trimWorkingSet()
            }
        }
    }

    // A pending close-to-tray callback must not undo a later activation.
    property int mainActivationEpoch: 0
    property var pendingTrayCloseTarget: null
    function showMain() {
        mainActivationEpoch++
        trayTrimTimer.stop()
        // A cleaner close may already have been approved, leaving its UI in
        // shutdown state while tray teardown waits for Qt.callLater. Restore
        // that UI before allowing another close or cleaner launch.
        if (pendingTrayCloseTarget) {
            const target = pendingTrayCloseTarget
            pendingTrayCloseTarget = null
            if (mainLoader.item === target) target.resumeSa6iAfterTrayReactivation()
        }
        if (!mainLoader.active || !mainLoader.item) {
            mainLoader.active = false
            mainLoader.active = true
        } else {
            // Reactivation is also an intent to keep the main window open if
            // a prior close-to-tray is still waiting for cleaner shutdown.
            mainLoader.item.cancelSa6iTrayCloseForReactivation()
            mainLoader.item.bringToFront()
        }
    }

    function onMainClosed() {
        const action = (Qt.platform.os === "osx" || !Preferences.closeToTray) ? "quit" : "tray"
        if (mainLoader.item && mainLoader.item.requestSa6iClose(action)) return
        finishMainClose(action)
    }

    function finishMainClose(action) {
        if (action !== "quit" && action !== "tray") return
        const target = mainLoader.item
        if (target && target.sa6iCleanBackend && target.sa6iCleanBackend.processTracked) {
            console.warn("Refusing to close while Sa6i Clean is still tracked")
            return
        }
        if (mainLoader.active && target) target.saveWindowState()
        if (action === "quit") {
            if (target && target.sa6iCleanBackend) {
                // The first close event can still be on the native stack.
                // Defer the approved quit and recheck ownership before Qt
                // sends its own close event to this window.
                Qt.callLater(() => {
                    if (mainLoader.item !== target || !target.sa6iCleanBackend
                            || target.sa6iCleanBackend.processTracked) return
                    if (!target.sa6iQuitAfterGate())
                        console.warn("Refusing application quit while Sa6i Clean is still tracked")
                })
            } else {
                Qt.quit()
            }
            return
        }
        // Unload after the close event has finished; recheck ownership and
        // activation in case another callback ran while teardown was queued.
        const activationEpoch = mainActivationEpoch
        pendingTrayCloseTarget = target
        Qt.callLater(() => {
            if (mainActivationEpoch !== activationEpoch || mainLoader.item !== target) return
            if (target && target.sa6iCleanBackend && target.sa6iCleanBackend.processTracked) {
                console.warn("Refusing deferred teardown while Sa6i Clean is tracked")
                return
            }
            if (target && !target.releaseAndTeardown()) return
            pendingTrayCloseTarget = null
            mainLoader.active = false
            trayTrimTimer.restart()
        })
    }

    Component.onCompleted: {
        Mirror.windowsChanged.connect(app.syncMirrorWindows)
        AppController.shelfOpenChanged.connect(app.syncShelfWindow)
        Preferences.islandChanged.connect(app.syncIslandWindow)
        app.syncMirrorWindows()
        app.syncShelfWindow()
        app.syncIslandWindow()
        if (!startMinimized)
            showMain()
        else
            trayTrimTimer.restart()
    }

    // Qt follows the system color scheme unless told otherwise; the window
    // frame and Mica tint must follow the app's theme instead.
    readonly property Binding colorScheme: Binding {
        target: Qt.styleHints
        property: "colorScheme"
        value: Theme.dark ? Qt.ColorScheme.Dark : Qt.ColorScheme.Light
    }

    readonly property Connections controller: Connections {
        target: AppController
        function onActivateRequested() { app.showMain() }
        function onQuitRequested() {
            if (mainLoader.item && mainLoader.item.requestSa6iClose("quit")) return
            app.finishMainClose("quit")
        }
        function onRingingFromChanged() {
            if (AppController.ringingFrom.length > 0) {
                app.showMain()
                if (app.mainWindow)
                    app.mainWindow.flash()
            }
        }
        function onRemotePromptDeviceIdChanged() {
            if (AppController.remotePromptDeviceId.length > 0) {
                app.showMain()
                if (app.mainWindow)
                    app.mainWindow.flash()
            }
        }
        function onShelfOpenChanged() {
            app.syncShelfWindow()
        }
    }
}
