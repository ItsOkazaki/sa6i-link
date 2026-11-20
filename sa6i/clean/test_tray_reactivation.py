"""Exercise the real QML coordinator and cleaner integration with fake OS/backend.

The app close functions are extracted verbatim; preferences, NativeWindow and
cleaner process are stand-ins. No real Windows, Qt SDK, or Sa6i Link build.
"""
import os
from pathlib import Path
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
try:
    from PySide6.QtCore import QObject, QPoint, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtTest import QTest
except ModuleNotFoundError:
    QGuiApplication = None

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipIf(QGuiApplication is None, 'requires PySide6')
class TrayReactivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.engine = QQmlEngine()
        source = (ROOT / 'desktop/app/qml/App.qml').read_text(encoding='utf-8')
        start = source.index('    property int mainActivationEpoch:')
        end = source.index('\n    Component.onCompleted:', start)
        functions = source[start:end].replace('Preferences.closeToTray', 'mockPreferences.closeToTray')
        main_source = (ROOT / 'desktop/app/qml/MainWindow.qml').read_text(encoding='utf-8')
        forward_start = main_source.index('    function resumeSa6iAfterTrayReactivation() {')
        forward_end = main_source.index('    Loader {', forward_start)
        forwarders = main_source[forward_start:forward_end]
        path = QUrl.fromLocalFile(str(ROOT / 'desktop/app/qml/components')).toString()
        qml = '''import QtQuick
import QtQuick.Window
import "''' + path + '''"
Window {
    id: window
    width: 800; height: 600; visible: true
    property bool autoReactivate: true
    property bool closeImmediatelyAfterReactivation: false
    property int teardownCount: 0
    property int activationCount: 0
    property var coordinator: app
    property var integrationObject: integration
    property var sa6iCleanBackend: backend
    property QtObject mockBackend: QtObject {
        id: backend
        property bool initialized: true
        property bool processTracked: true
        property string status: "attached"
        property int error: 0
        property int starts: 0
        property bool cancelFails: false
        function poll() {}
        function requestClose() {
            if (processTracked) { status = "closing"; return false }
            status = "closed"; return true
        }
        function cancelClose() {
            if (cancelFails || status !== "closing" || !processTracked) return false
            status = "attached"; return true
        }
        function start(path) { starts++; processTracked = true; status = "launching"; return true }
    }
    property QtObject cleanLoader: QtObject { id: sa6iCleanLoader; property var item: integration }
    function requestSa6iClose(action) { return integration.requestClose(action) }
''' + forwarders + '''
    function bringToFront() { activationCount++ }
    function saveWindowState() {}
    function releaseAndTeardown() { teardownCount++; return true }
    function addCaptionHole(item) {}
    function removeCaptionHole(item) {}
    function sa6iBindCleanParent() { backend.status = "idle"; return true }
    function sa6iSyncCleanViewport(item, selected) { return true }
    property QtObject coordinatorObject: QtObject {
        id: app
        property QtObject mockPreferences: QtObject { property bool closeToTray: true }
        property QtObject mainLoader: QtObject { property bool active: true; property var item: window }
        property Timer trayTrimTimer: Timer { interval: 100000 }
''' + functions + '''
    }
    Sa6iCleanIntegration {
        id: integration
        anchors.fill: parent
        hostWindow: window
        testDirectory: "C:/test"
        onCloseApproved: (action) => {
            app.finishMainClose(action)
            // Simulate activation immediately after approval, before callLater.
            if (window.autoReactivate) {
                app.showMain()
                if (window.closeImmediatelyAfterReactivation) {
                    window.closeImmediatelyAfterReactivation = false
                    window.autoReactivate = false
                    app.onMainClosed()
                }
            }
        }
    }
}'''
        cls.component = QQmlComponent(cls.engine)
        cls.component.setData(qml.encode('utf-8'), QUrl())
        if cls.component.isError():
            raise AssertionError('\n'.join(e.toString() for e in cls.component.errors()))

    def setUp(self):
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [e.toString() for e in self.component.errors()])
        self.backend = self.window.property('sa6iCleanBackend')
        self.integration = self.window.property('integrationObject')
        self.coordinator = self.window.property('coordinator')
        self.loader = self.coordinator.property('mainLoader')

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_clean_view_uses_single_integrated_header_and_back_button(self):
        self.integration.setProperty('cleanOpen', True)
        self.app.processEvents()
        header = self.window.findChild(QObject, 'cleanIntegratedHeader')
        button = self.window.findChild(QObject, 'cleanBackButton')
        viewport = self.window.findChild(QObject, 'cleanNativeViewport')
        self.assertIsNotNone(header)
        self.assertIsNotNone(button)
        self.assertIsNotNone(viewport)
        self.assertTrue(header.property('visible'))
        self.assertEqual(header.property('height'), 48)
        self.assertEqual(viewport.property('y'), 0)
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(30, 24))
        self.app.processEvents()
        self.assertFalse(self.integration.property('cleanOpen'))
        self.assertFalse(header.property('visible'))
        self.assertTrue(self.backend.property('processTracked'))

    def approve_and_reactivate(self):
        self.integration.setProperty('cleanOpen', True)
        self.coordinator.onMainClosed()
        self.assertTrue(self.integration.property('closePending'))
        self.assertTrue(self.backend.property('processTracked'))
        self.backend.setProperty('processTracked', False)
        QTest.qWait(150)
        self.assertEqual(self.window.property('activationCount'), 1)
        self.assertEqual(self.window.property('teardownCount'), 0)
        self.assertTrue(self.loader.property('active'))
        self.assertFalse(self.integration.property('closePending'))
        self.assertFalse(self.integration.property('shuttingDown'))
        self.assertFalse(self.integration.property('cleanOpen'))

    def test_reactivation_restores_entry_and_allows_fresh_launch(self):
        self.approve_and_reactivate()
        self.assertEqual(self.backend.property('status'), 'closed')
        self.integration.openClean()
        self.assertEqual(self.backend.property('starts'), 1)
        self.assertTrue(self.backend.property('processTracked'))
        self.assertTrue(self.integration.property('cleanOpen'))

    def test_new_close_after_reactivation_can_still_teardown(self):
        self.approve_and_reactivate()
        self.window.setProperty('autoReactivate', False)
        self.coordinator.onMainClosed()
        QTest.qWait(30)
        self.assertEqual(self.window.property('teardownCount'), 1)
        self.assertFalse(self.loader.property('active'))

    def test_immediate_second_close_before_deferred_teardown_is_honored(self):
        self.window.setProperty('closeImmediatelyAfterReactivation', True)
        self.coordinator.onMainClosed()
        self.assertTrue(self.integration.property('closePending'))
        self.backend.setProperty('processTracked', False)
        # A reentrant gate request advances on its next 100 ms timer tick.
        QTest.qWait(300)
        self.assertEqual(self.window.property('activationCount'), 1)
        self.assertEqual(self.window.property('teardownCount'), 1)
        self.assertFalse(self.loader.property('active'))

    def test_reactivation_cancels_pending_tray_but_keeps_process_tracked(self):
        self.integration.setProperty('cleanOpen', True)
        self.coordinator.onMainClosed()
        self.assertTrue(self.integration.property('closePending'))
        self.coordinator.showMain()
        self.assertFalse(self.integration.property('closePending'))
        self.assertFalse(self.integration.property('shuttingDown'))
        self.assertTrue(self.backend.property('processTracked'))
        self.assertEqual(self.backend.property('status'), 'attached')
        self.backend.setProperty('processTracked', False)  # A posted WM_CLOSE can still complete.
        QTest.qWait(150)
        self.assertTrue(self.loader.property('active'))
        self.assertEqual(self.window.property('teardownCount'), 0)

    def test_reactivation_intent_survives_cancel_failure_and_exit(self):
        self.backend.setProperty('cancelFails', True)
        self.coordinator.onMainClosed()
        self.coordinator.showMain()
        self.assertTrue(self.integration.property('closePending'))
        self.backend.setProperty('processTracked', False)
        QTest.qWait(150)
        self.assertFalse(self.integration.property('closePending'))
        self.assertFalse(self.integration.property('shuttingDown'))
        self.assertEqual(self.window.property('teardownCount'), 0)
        self.assertTrue(self.loader.property('active'))

    def test_reactivation_does_not_cancel_pending_quit(self):
        self.assertTrue(self.integration.requestClose('quit'))
        self.assertTrue(self.integration.property('closePending'))
        self.coordinator.showMain()
        self.assertTrue(self.integration.property('closePending'))
        self.assertTrue(self.backend.property('processTracked'))
        self.assertEqual(self.backend.property('status'), 'closing')

    def test_resume_refuses_while_process_is_tracked(self):
        self.integration.setProperty('shuttingDown', True)
        self.assertFalse(self.integration.resumeAfterTrayReactivation())
        self.assertTrue(self.integration.property('shuttingDown'))
        self.assertTrue(self.backend.property('processTracked'))


if __name__ == '__main__':
    unittest.main()
