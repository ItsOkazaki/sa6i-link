# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen test of the real Hub QML block with mock components and backend.

This is not the full application, native window, real cleaner or Windows test.
"""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtCore import QPoint, QPointF, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
except ModuleNotFoundError:
    QGuiApplication = None

ROOT = Path(__file__).resolve().parents[2]

@unittest.skipIf(QGuiApplication is None, 'requires PySide6')
class HubDashboardTests(unittest.TestCase):
    def test_dashboard_buttons_fit_and_switch_with_mock_backend(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        source = (ROOT / 'desktop/app/qml/MainWindow.qml').read_text(encoding='utf-8')
        start = source.index('    Item {\n        id: hubHome\n')
        end = source.index('    // ---- Overlays ----', start)
        body = source[start:end].replace('Theme.', 'theme.').replace('Icons.', 'icons.')
        body = body.replace('sa6iCleanLoader.item', 'cleaner')
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'Card.qml').write_text(
                'import QtQuick\nRectangle {property int padding: 16; '
                'default property alias content: inner.data; Item {id: inner; '
                'anchors.fill: parent; anchors.margins: parent.padding} }', encoding='utf-8')
            (directory / 'Txt.qml').write_text(
                'import QtQuick\nText {property string role; property bool muted: false; '
                'property real size: 16; font.pixelSize: size}', encoding='utf-8')
            (directory / 'Button.qml').write_text(
                'import QtQuick\nRectangle {property string text; property string iconPath; '
                'property string variant; signal clicked(); implicitWidth: 120; implicitHeight: 40; '
                'MouseArea {anchors.fill: parent; onClicked: parent.clicked()} }', encoding='utf-8')
            harness = '''import QtQuick
import QtQuick.Window
Window { id: window; width: 880; height: 600; visible: true
property bool hubActive: true
property color windowSurface: "white"
property alias cleaner: cleaner
property alias dashboard: hubHome
QtObject { id: theme; property int topBarHeight: 52; property int contentPadding: 22 }
QtObject { id: icons; property string phone: "phone"; property string sparkle: "sparkle" }
QtObject { id: captionButtons; property int width: 138 }
QtObject { id: cleaner; property bool cleanOpen: false; property bool available: true
    property bool externalOverlayOpen: false; property bool closePending: false
    property bool shuttingDown: false; function openClean() { cleanOpen = true } }
''' + body + '\n}'
            (directory / 'test.qml').write_text(harness, encoding='utf-8')
            engine = QQmlEngine()
            component = QQmlComponent(engine, QUrl.fromLocalFile(str(directory / 'test.qml')))
            if component.isError():
                self.fail('\n'.join(e.toString() for e in component.errors()))
            window = component.create()
            self.assertIsNotNone(window, [e.toString() for e in component.errors()])
            app.processEvents()
            link = window.findChild(QQuickItem, 'hubOpenLink')
            clean = window.findChild(QQuickItem, 'hubOpenClean')
            self.assertIsNotNone(link)
            self.assertIsNotNone(clean)
            for button in (link, clean):
                position = button.mapToScene(QPointF(0, 0))
                self.assertGreater(button.width(), 0)
                self.assertGreater(button.height(), 0)
                self.assertGreaterEqual(position.x(), 0)
                self.assertGreaterEqual(position.y(), 52)
                self.assertLessEqual(position.x() + button.width(), 880)
                self.assertLessEqual(position.y() + button.height(), 600)
            point = link.mapToScene(QPointF(10, 10))
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))
            app.processEvents()
            self.assertFalse(window.property('hubActive'))
            window.setProperty('hubActive', True)
            app.processEvents()
            point = clean.mapToScene(QPointF(10, 10))
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))
            app.processEvents()
            self.assertTrue(window.property('cleaner').property('cleanOpen'))
            self.assertFalse(window.property('dashboard').property('visible'))
            window.close()
            window.deleteLater()
            app.processEvents()

if __name__ == '__main__':
    unittest.main()
