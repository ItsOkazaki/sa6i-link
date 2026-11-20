"""Exercise App.qml's actual close functions with stand-in QML objects.

Not the real App, NativeWindow, Win32 or a production shutdown test. Requires
PySide6 and a working Qt Quick platform; uses a separate in-memory component.
"""
import os
from pathlib import Path
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
try:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtTest import QSignalSpy, QTest
except ModuleNotFoundError:
    QGuiApplication = None

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipIf(QGuiApplication is None, 'requires PySide6')
class AppCloseWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.engine = QQmlEngine()
        source = (ROOT / 'desktop/app/qml/App.qml').read_text(encoding='utf-8')
        start = source.index('    property int mainActivationEpoch:')
        end = source.index('\n    Component.onCompleted:', start)
        functions = source[start:end].replace('Preferences.closeToTray', 'mockPreferences.closeToTray')
        quit_start = source.index('        function onQuitRequested() {')
        quit_end = source.index('\n        function onRingingFromChanged()', quit_start)
        quit_handler = source[quit_start:quit_end]
        qml = '''import QtQuick
import QtQml
QtObject {
    id: app
    property QtObject mockPreferences: QtObject { property bool closeToTray: true }
    property QtObject backend: QtObject { property bool processTracked: false }
    property QtObject target: QtObject {
        property var sa6iCleanBackend: null
        property bool acceptsClose: false
        property string lastAction: ""
        property int saved: 0
        property int teardownCalls: 0
        property int approvedQuitCalls: 0
        property bool approveQuitResult: true
        property int activations: 0
        property int resumptions: 0
        property bool teardownResult: true
        function requestSa6iClose(action) { lastAction = action; return acceptsClose }
        function resumeSa6iAfterTrayReactivation() { resumptions++ }
        function cancelSa6iTrayCloseForReactivation() {}
        function bringToFront() { activations++ }
        function saveWindowState() { saved++ }
        function releaseAndTeardown() { teardownCalls++; return teardownResult }
        function sa6iQuitAfterGate() {
            approvedQuitCalls++
            if (!approveQuitResult || (sa6iCleanBackend && sa6iCleanBackend.processTracked)) return false
            Qt.quit()
            return true
        }
    }
    property QtObject mainLoader: QtObject { property bool active: true; property var item: app.target }
    property Timer trayTrimTimer: Timer { interval: 100000 }
    readonly property bool timerRunning: trayTrimTimer.running
    property QtObject mockController: QtObject { signal quitRequested() }
    property Connections controllerConnection: Connections {
        target: mockController
''' + quit_handler + '''
    }
''' + functions + '\n}'
        cls.component = QQmlComponent(cls.engine)
        cls.component.setData(qml.encode('utf-8'), QUrl())
        if cls.component.isError():
            raise AssertionError('\n'.join(e.toString() for e in cls.component.errors()))

    def setUp(self):
        self.root = self.component.create()
        self.assertIsNotNone(self.root, [e.toString() for e in self.component.errors()])
        self.target = self.root.property('target')
        self.backend = self.root.property('backend')
        self.loader = self.root.property('mainLoader')

    def tearDown(self):
        self.root.deleteLater()
        self.app.processEvents()

    def wait_deferred(self):
        QTest.qWait(20)

    def test_tray_without_cleaner_saves_then_defers_teardown(self):
        self.root.onMainClosed()
        self.assertEqual(self.target.property('lastAction'), 'tray')
        self.assertEqual(self.target.property('saved'), 1)
        self.assertTrue(self.loader.property('active'))
        self.assertEqual(self.target.property('teardownCalls'), 0)
        self.wait_deferred()
        self.assertEqual(self.target.property('teardownCalls'), 1)
        self.assertFalse(self.loader.property('active'))
        self.assertTrue(self.root.property('timerRunning'))

    def test_pending_request_and_direct_finish_do_not_close_tracked_process(self):
        self.target.setProperty('sa6iCleanBackend', self.backend)
        self.target.setProperty('acceptsClose', True)
        self.backend.setProperty('processTracked', True)
        self.root.onMainClosed()
        self.wait_deferred()
        self.assertEqual(self.target.property('saved'), 0)
        self.assertEqual(self.target.property('teardownCalls'), 0)
        self.root.finishMainClose('tray')
        self.wait_deferred()
        self.assertTrue(self.loader.property('active'))
        self.assertEqual(self.target.property('saved'), 0)
        self.backend.setProperty('processTracked', False)
        self.root.finishMainClose('tray')
        self.wait_deferred()
        self.assertEqual(self.target.property('saved'), 1)
        self.assertEqual(self.target.property('teardownCalls'), 1)
        self.assertFalse(self.loader.property('active'))

    def test_deferred_teardown_rechecks_tracking_and_window_identity(self):
        self.target.setProperty('sa6iCleanBackend', self.backend)
        self.root.finishMainClose('tray')
        self.backend.setProperty('processTracked', True)
        self.wait_deferred()
        self.assertTrue(self.loader.property('active'))
        self.assertEqual(self.target.property('teardownCalls'), 0)
        self.backend.setProperty('processTracked', False)
        self.root.finishMainClose('tray')
        self.loader.setProperty('item', None)
        self.wait_deferred()
        self.assertTrue(self.loader.property('active'))
        self.assertEqual(self.target.property('teardownCalls'), 0)

    def test_reactivation_cancels_deferred_tray_teardown(self):
        self.target.setProperty('sa6iCleanBackend', self.backend)
        self.root.finishMainClose('tray')
        self.assertEqual(self.target.property('saved'), 1)
        self.root.showMain()  # Activation comes before Qt.callLater executes.
        self.assertEqual(self.target.property('activations'), 1)
        self.assertEqual(self.target.property('resumptions'), 1)
        self.wait_deferred()
        self.assertTrue(self.loader.property('active'))
        self.assertEqual(self.target.property('teardownCalls'), 0)
        self.assertFalse(self.root.property('timerRunning'))
        # A later deliberate close still works.
        self.root.finishMainClose('tray')
        self.wait_deferred()
        self.assertEqual(self.target.property('teardownCalls'), 1)
        self.assertFalse(self.loader.property('active'))

    def test_native_teardown_refusal_keeps_loader_active(self):
        self.target.setProperty('teardownResult', False)
        self.root.finishMainClose('tray')
        self.wait_deferred()
        self.assertEqual(self.target.property('teardownCalls'), 1)
        self.assertTrue(self.loader.property('active'))
        self.assertFalse(self.root.property('timerRunning'))

    def test_controller_quit_uses_gate_then_waits_for_approval(self):
        spy = QSignalSpy(self.engine.quit)
        self.target.setProperty('sa6iCleanBackend', self.backend)
        self.target.setProperty('acceptsClose', True)
        self.backend.setProperty('processTracked', True)
        self.root.property('mockController').quitRequested.emit()
        self.assertEqual(self.target.property('lastAction'), 'quit')
        self.assertEqual(spy.count(), 0)
        self.assertEqual(self.target.property('saved'), 0)
        self.backend.setProperty('processTracked', False)
        self.root.finishMainClose('quit')  # Simulate close-approved signal.
        self.assertEqual(spy.count(), 0)  # Wait until the original close event unwinds.
        self.wait_deferred()
        self.assertEqual(spy.count(), 1)
        self.assertEqual(self.target.property('approvedQuitCalls'), 1)
        self.assertEqual(self.target.property('saved'), 1)

    def test_controller_quit_fails_closed_when_request_declined_but_tracked(self):
        spy = QSignalSpy(self.engine.quit)
        self.target.setProperty('sa6iCleanBackend', self.backend)
        self.backend.setProperty('processTracked', True)
        self.root.property('mockController').quitRequested.emit()
        self.assertEqual(self.target.property('lastAction'), 'quit')
        self.assertEqual(spy.count(), 0)
        self.assertEqual(self.target.property('saved'), 0)

    def test_controller_quit_without_window(self):
        spy = QSignalSpy(self.engine.quit)
        self.loader.setProperty('item', None)
        self.root.property('mockController').quitRequested.emit()
        self.assertEqual(spy.count(), 1)
        self.assertEqual(self.target.property('saved'), 0)

    def test_quit_signal_only_after_process_is_untracked(self):
        spy = QSignalSpy(self.engine.quit)
        self.target.setProperty('sa6iCleanBackend', self.backend)
        self.backend.setProperty('processTracked', True)
        self.root.finishMainClose('quit')
        self.assertEqual(spy.count(), 0)
        self.backend.setProperty('processTracked', False)
        self.root.finishMainClose('quit')
        self.assertEqual(spy.count(), 0)
        self.wait_deferred()
        self.assertEqual(spy.count(), 1)
        self.assertEqual(self.target.property('saved'), 1)
        self.assertTrue(self.loader.property('active'))

    def test_deferred_quit_rechecks_process_and_window(self):
        spy = QSignalSpy(self.engine.quit)
        self.target.setProperty('sa6iCleanBackend', self.backend)
        self.root.finishMainClose('quit')
        self.backend.setProperty('processTracked', True)
        self.wait_deferred()
        self.assertEqual(spy.count(), 0)
        self.assertEqual(self.target.property('approvedQuitCalls'), 0)
        self.backend.setProperty('processTracked', False)
        self.root.finishMainClose('quit')
        self.loader.setProperty('item', None)
        self.wait_deferred()
        self.assertEqual(spy.count(), 0)
        self.assertEqual(self.target.property('approvedQuitCalls'), 0)

    def test_native_refusal_prevents_quit(self):
        spy = QSignalSpy(self.engine.quit)
        self.target.setProperty('sa6iCleanBackend', self.backend)
        self.target.setProperty('approveQuitResult', False)
        self.root.finishMainClose('quit')
        self.wait_deferred()
        self.assertEqual(self.target.property('approvedQuitCalls'), 1)
        self.assertEqual(spy.count(), 0)

    def test_unknown_action_does_nothing(self):
        self.root.finishMainClose('unknown')
        self.wait_deferred()
        self.assertEqual(self.target.property('saved'), 0)
        self.assertEqual(self.target.property('teardownCalls'), 0)
        self.assertTrue(self.loader.property('active'))


if __name__ == '__main__':
    unittest.main()
