"""Optional offscreen Qt Quick tests; install PySide6-Essentials to run."""
import os
from pathlib import Path
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
try:
    import PySide6  # noqa: F401
except ModuleNotFoundError:
    QGuiApplication = None
else:
    # Missing native Qt dependencies are errors, not silently skipped tests.
    from PySide6.QtCore import QPoint, QUrl, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow
    from PySide6.QtTest import QSignalSpy, QTest


@unittest.skipIf(QGuiApplication is None, 'PySide6-Essentials not installed')
class CleanViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.engine = QQmlEngine()
        cls.component = QQmlComponent(cls.engine, QUrl.fromLocalFile(str(Path(__file__).with_name('CleanView.qml'))))
        if cls.component.isError():
            raise AssertionError('\n'.join(str(e.toString()) for e in cls.component.errors()))

    def setUp(self):
        self.window = QQuickWindow()
        self.window.resize(880, 600)
        self.view = self.component.create()
        self.assertIsNotNone(self.view, [e.toString() for e in self.component.errors()])
        self.view.setParentItem(self.window.contentItem())
        self.view.setWidth(880)
        self.view.setHeight(600)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.view.deleteLater()
        self.window.deleteLater()
        self.app.processEvents()

    def test_viewport_tracks_size_and_starts_with_explicit_status(self):
        self.assertFalse(self.view.isVisible())
        self.assertFalse(self.view.property('embedded'))
        self.assertEqual(self.view.property('statusMessage'), 'Sa6i Clean is not connected.')
        self.view.setProperty('active', True)
        self.app.processEvents()
        viewport = self.view.property('viewport')
        self.assertTrue(self.view.isVisible())
        self.assertEqual((viewport.x(), viewport.y(), viewport.width(), viewport.height()), (0, 56, 880, 544))
        self.view.setWidth(1024)
        self.view.setHeight(750)
        self.app.processEvents()
        self.assertEqual((viewport.width(), viewport.height()), (1024, 694))
        self.view.setProperty('active', False)
        self.app.processEvents()
        self.assertFalse(viewport.isVisible())

    def test_status_is_visible_until_embedded_and_reports_failure(self):
        self.view.setProperty('active', True)
        self.view.setProperty('statusMessage', 'Could not attach cleaner')
        self.app.processEvents()
        status = self.view.findChild(QQuickItem, 'cleanHostStatus')
        self.assertIsNotNone(status)
        self.assertTrue(status.isVisible())
        self.assertEqual(status.property('text'), 'Could not attach cleaner')
        self.view.setProperty('embedded', True)
        self.app.processEvents()
        self.assertFalse(status.isVisible())
        self.view.setProperty('embedded', False)
        self.app.processEvents()
        self.assertTrue(status.isVisible())

    def test_back_button_emits_without_changing_owner_state(self):
        self.view.setProperty('active', True)
        self.app.processEvents()
        spy = QSignalSpy(self.view.backRequested)
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(30, 28))
        self.app.processEvents()
        self.assertEqual(spy.count(), 1)
        # The parent must choose when to hide the view and its native child.
        self.assertTrue(self.view.property('active'))


@unittest.skipIf(QGuiApplication is None, 'PySide6-Essentials not installed')
class CleanEntryTests(unittest.TestCase):
    def test_entry_emits_only_when_available(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        engine = QQmlEngine()
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(Path(__file__).with_name('CleanEntry.qml'))))
        self.assertFalse(component.isError(), [e.toString() for e in component.errors()])
        window = QQuickWindow()
        window.resize(200, 80)
        entry = component.create()
        self.assertIsNotNone(entry, [e.toString() for e in component.errors()])
        entry.setParentItem(window.contentItem())
        entry.setWidth(160)
        entry.setHeight(40)
        window.show()
        app.processEvents()
        spy = QSignalSpy(entry.openRequested)
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(20, 20))
        self.assertEqual(spy.count(), 1)
        entry.forceActiveFocus()
        QTest.keyClick(window, Qt.Key_Return)
        self.assertEqual(spy.count(), 2)
        entry.setProperty('available', False)
        app.processEvents()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(20, 20))
        QTest.keyClick(window, Qt.Key_Return)
        self.assertEqual(spy.count(), 2)
        window.close()
        entry.deleteLater()
        window.deleteLater()
        app.processEvents()


if __name__ == '__main__':
    unittest.main()
