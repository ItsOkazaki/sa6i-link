"""Offscreen QML close coordination tests with a fake adapter, not Win32."""
from pathlib import Path
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
try:
    import PySide6  # noqa: F401
except ModuleNotFoundError:
    QGuiApplication = None
else:
    from PySide6.QtCore import QCoreApplication, QEvent, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtTest import QSignalSpy, QTest


@unittest.skipIf(QGuiApplication is None, 'PySide6-Essentials not installed')
class CloseGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.engine = QQmlEngine()
        path = Path(__file__).parent / 'tests' / 'CloseGateHarness.qml'
        cls.component = QQmlComponent(cls.engine, QUrl.fromLocalFile(str(path)))
        if cls.component.isError():
            raise AssertionError('\n'.join(e.toString() for e in cls.component.errors()))

    def setUp(self):
        self.root = self.component.create()
        self.assertIsNotNone(self.root, [e.toString() for e in self.component.errors()])
        self.gate = self.root.property('gate')
        self.backend = self.root.property('backend')
        self.approved = QSignalSpy(self.gate.closeApproved)
        self.cancelled = QSignalSpy(self.gate.closeCancelled)
        self.errors = QSignalSpy(self.gate.gateError)

    def tearDown(self):
        self.root.deleteLater()
        self.app.processEvents()

    def test_immediate_and_delayed_close_and_duplicate_requests(self):
        self.assertFalse(self.gate.request('invalid'))
        self.assertTrue(self.gate.request('tray'))
        self.assertTrue(self.gate.property('pending'))
        self.assertFalse(self.gate.request('quit'))
        self.assertEqual(self.gate.property('pendingAction'), 'tray')
        self.assertEqual(self.approved.count(), 0)
        self.backend.setProperty('alive', False)
        self.gate.advance()
        self.assertFalse(self.gate.property('pending'))
        self.assertEqual(self.approved.count(), 1)
        self.assertEqual(self.approved.at(0)[0], 'tray')
        self.gate.advance()
        self.assertEqual(self.approved.count(), 1)
        self.assertTrue(self.gate.request('quit'))
        self.assertEqual(self.approved.at(1)[0], 'quit')

    def test_cancel_live_and_late_exit(self):
        self.assertTrue(self.gate.request('quit'))
        self.assertTrue(self.gate.keepOpen())
        self.assertEqual(self.cancelled.count(), 1)
        self.assertFalse(self.backend.property('closing'))
        self.assertEqual(self.approved.count(), 0)
        # The previously sent OS message cannot be recalled. An eventual exit
        # must be handled by the backend even after this gate has finished.
        self.backend.setProperty('alive', False)
        self.gate.advance()
        self.assertEqual(self.approved.count(), 0)
        self.assertFalse(self.gate.keepOpen())

    def test_cancel_intent_survives_wait_failure_and_exit(self):
        self.assertTrue(self.gate.request('tray'))
        self.backend.setProperty('waitFails', True)
        self.assertTrue(self.gate.keepOpen())
        self.assertTrue(self.gate.property('pending'))
        self.assertFalse(self.gate.request('quit'))
        self.backend.setProperty('alive', False)
        self.gate.advance()
        self.assertTrue(self.gate.property('pending'))
        self.backend.setProperty('waitFails', False)
        self.gate.advance()
        self.assertFalse(self.gate.property('pending'))
        self.assertEqual(self.cancelled.count(), 1)
        self.assertEqual(self.approved.count(), 0)

    def test_cancel_retries_when_process_is_still_alive(self):
        self.assertTrue(self.gate.request('tray'))
        self.backend.setProperty('cancelFails', True)
        self.assertTrue(self.gate.keepOpen())
        self.assertTrue(self.gate.property('pending'))
        self.assertEqual(self.cancelled.count(), 0)
        self.backend.setProperty('cancelFails', False)
        self.gate.advance()
        self.assertFalse(self.gate.property('pending'))
        self.assertEqual(self.cancelled.count(), 1)
        self.assertEqual(self.approved.count(), 0)
        self.assertTrue(self.backend.property('alive'))
        self.assertFalse(self.backend.property('closing'))

    def test_fail_closed_on_exception_and_non_boolean(self):
        self.backend.setProperty('throwOnPoll', True)
        self.assertTrue(self.gate.request('quit'))
        self.assertTrue(self.gate.property('pending'))
        self.assertEqual(self.errors.count(), 1)
        self.backend.setProperty('throwOnPoll', False)
        self.backend.setProperty('nonBooleanResult', True)
        self.gate.advance()
        self.assertTrue(self.gate.property('pending'))
        self.assertEqual(self.approved.count(), 0)
        self.backend.setProperty('nonBooleanResult', False)
        self.backend.setProperty('alive', False)
        self.gate.advance()
        self.assertEqual(self.approved.count(), 1)

    def test_keeps_original_backend_if_owner_changes_property(self):
        self.assertTrue(self.gate.request('quit'))
        self.gate.setProperty('backend', None)
        self.backend.setProperty('alive', False)
        self.gate.advance()
        self.assertEqual(self.approved.count(), 1)
        self.assertFalse(self.gate.request('tray'))

    def test_destroyed_backend_never_approves_close(self):
        self.assertTrue(self.gate.request('tray'))
        self.backend.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.gate.advance()
        self.assertTrue(self.gate.property('pending'))
        self.assertEqual(self.approved.count(), 0)
        self.assertGreaterEqual(self.errors.count(), 1)

    def test_reentrant_cancel_does_not_approve_close(self):
        self.backend.setProperty('alive', False)
        self.backend.setProperty('reenterKeepOpen', True)
        self.assertTrue(self.gate.request('quit'))
        self.assertEqual(self.approved.count(), 0)
        self.assertEqual(self.cancelled.count(), 1)

    def test_timer_continues_polling_until_exit(self):
        self.gate.setProperty('pollInterval', 10)
        self.assertTrue(self.gate.request('quit'))
        self.backend.setProperty('alive', False)
        QTest.qWait(100)
        self.assertEqual(self.approved.count(), 1)
        self.assertFalse(self.gate.property('pending'))


if __name__ == '__main__':
    unittest.main()
