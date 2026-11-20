"""Offscreen layout checks only: not a Windows 7 compositor test."""
import os
from pathlib import Path
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
try:
    from PySide6.QtCore import QObject, QPointF, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem
except ModuleNotFoundError:
    QGuiApplication = None


@unittest.skipIf(QGuiApplication is None, 'requires PySide6')
class HeaderClearanceTests(unittest.TestCase):
    def test_opt_in_clearance_reserves_space_below_header(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        engine = QQmlEngine()
        path = Path(__file__).parent / 'tests' / 'AppIntegrationHarness.qml'
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
        self.assertFalse(component.isError(), [e.toString() for e in component.errors()])
        window = component.create()
        self.assertIsNotNone(window, [e.toString() for e in component.errors()])
        try:
            integration = window.property('integrationObject')
            integration.setProperty('cleanOpen', True)
            app.processEvents()
            header = window.findChild(QQuickItem, 'cleanIntegratedHeader')
            clearance = window.findChild(QQuickItem, 'cleanHeaderClearance')
            viewport = window.findChild(QQuickItem, 'cleanNativeViewport')
            self.assertIsNotNone(header)
            self.assertIsNotNone(clearance)
            self.assertIsNotNone(viewport)
            self.assertEqual(viewport.mapToScene(QPointF(0, 0)).y(), 48)
            self.assertEqual(header.height(), 48)
            self.assertEqual(clearance.height(), 0)
            integration.setProperty('headerClearance', 40)
            app.processEvents()
            self.assertEqual(header.height(), 48)
            self.assertEqual(clearance.height(), 40)
            self.assertEqual(viewport.mapToScene(QPointF(0, 0)).y(), 88)
            self.assertEqual(viewport.height(), 512)
            integration.setProperty('headerClearance', -20)
            app.processEvents()
            self.assertEqual(clearance.height(), 0)
            self.assertEqual(viewport.mapToScene(QPointF(0, 0)).y(), 48)
            integration.setProperty('headerClearance', 1000)
            app.processEvents()
            self.assertEqual(clearance.height(), 552)
            self.assertEqual(viewport.height(), 0)
        finally:
            window.close()
            window.deleteLater()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
