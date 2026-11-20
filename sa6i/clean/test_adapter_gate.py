"""QML + Qt C++ adapter + fake-Win32 C backend, never a Windows test.

Set SA6I_QT_ADAPTER_TEST_LIB to the explicitly built test shared library.
It must use the same Qt runtime as PySide6. Missing libraries are not skipped.
"""
import ctypes
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
    import shiboken6
    from PySide6.QtCore import QObject, QPoint, Qt, QUrl, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtTest import QSignalSpy, QTest

LIB = os.environ.get('SA6I_QT_ADAPTER_TEST_LIB')


if QGuiApplication is not None:
    class BindAdapterHook(QObject):
        """Fake NativeWindow's C++-only parent rebind for this test harness."""
        def __init__(self, library, address):
            super().__init__()
            self.library = library
            self.address = address

        @Slot(result=bool)
        def bind(self):
            return bool(self.library.test_adapter_bind(self.address))


@unittest.skipIf(QGuiApplication is None or not LIB, 'requires PySide6 and SA6I_QT_ADAPTER_TEST_LIB')
class AdapterGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.engine = QQmlEngine()
        cls.component = QQmlComponent(cls.engine, QUrl.fromLocalFile(str(
            Path(__file__).parent / 'tests' / 'AdapterGateHarness.qml')))
        if cls.component.isError():
            raise AssertionError('\n'.join(e.toString() for e in cls.component.errors()))
        cls.lib = ctypes.CDLL(LIB)
        cls.lib.test_adapter_create.restype = ctypes.c_void_p
        cls.lib.test_adapter_bind.argtypes = [ctypes.c_void_p]
        cls.lib.test_adapter_bind.restype = ctypes.c_bool
        cls.lib.test_adapter_destroy.argtypes = [ctypes.c_void_p]
        for name in ('simulation_reset', 'simulation_make_window', 'simulation_exit',
                     'simulation_block_reads', 'simulation_release_reads'):
            getattr(cls.lib, name).restype = None
        cls.lib.simulation_close_messages.restype = ctypes.c_int
        cls.lib.simulation_starts.restype = ctypes.c_int
        cls.lib.simulation_show.restype = ctypes.c_int
        cls.lib.simulation_set_fail_show.argtypes = [ctypes.c_int]
        cls.lib.simulation_set_fail_show.restype = None
        cls.lib.simulation_read_waiting.restype = ctypes.c_int

    def setUp(self):
        self.lib.simulation_reset()
        self.address = self.lib.test_adapter_create()
        self.assertTrue(self.address)
        self.assertTrue(self.lib.test_adapter_bind(self.address))
        self.adapter = shiboken6.wrapInstance(self.address, QObject)
        self.root = self.component.create()
        self.assertIsNotNone(self.root, [e.toString() for e in self.component.errors()])
        self.root.setProperty('adapter', self.adapter)
        self.gate = self.root.property('gate')
        self.approved = QSignalSpy(self.gate.closeApproved)
        self.cancelled = QSignalSpy(self.gate.closeCancelled)

    def wait_for_handoff(self):
        for _ in range(300):
            if not self.adapter.property('launchPending'):
                return
            QTest.qWait(10)
        self.fail('launch worker did not complete')

    def wait_for_blocked_read(self):
        for _ in range(300):
            if self.lib.simulation_read_waiting():
                return
            QTest.qWait(10)
        self.fail('worker did not reach fake read')

    def tearDown(self):
        # Ensure any worker has stopped before changing fake process state.
        self.lib.simulation_release_reads()
        self.wait_for_handoff()
        # Explicitly prove/reap fake process exit before deleting the adapter.
        self.lib.simulation_exit()
        self.root.adapterPoll()
        if self.gate.property('pending'):
            self.gate.keepOpen()
        self.root.setProperty('adapter', None)
        self.root.deleteLater()
        self.lib.test_adapter_destroy(self.address)
        self.app.processEvents()

    def test_main_window_overlay_binding_with_simulated_items(self):
        # Exercise the actual MainWindow binding expression, not a rewritten
        # copy. These are stand-in items, not the complete MainWindow.
        source = (Path(__file__).parents[2] / 'desktop/app/qml/MainWindow.qml').read_text(encoding='utf-8')
        start = source.index('externalOverlayOpen: ') + len('externalOverlayOpen: ')
        end = source.index('\n            onCloseApproved:', start)
        expression = source[start:end]
        names = ('pairingSheet', 'ringingSheet', 'remotePromptSheet',
                 'pcMirrorPromptSheet', 'continuityPasteSheet', 'doctorSheet', 'toast')
        declarations = '\n'.join(
            f'Item {{ id: {name}; objectName: "{name}"; visible: false }}' for name in names)
        qml = f'''import QtQuick
Item {{
    property bool overlayActive: {expression}
    {declarations}
    QtObject {{ id: doctorLoader; property var item: doctorSheet }}
    QtObject {{ id: commandPaletteLoader; objectName: "commandPaletteLoader"; property bool active: false }}
}}'''
        component = QQmlComponent(self.engine)
        component.setData(qml.encode('utf-8'), QUrl())
        obj = component.create()
        self.assertIsNotNone(obj, [e.toString() for e in component.errors()])
        try:
            self.assertFalse(obj.property('overlayActive'))
            for name in names + ('commandPaletteLoader',):
                child = obj.findChild(QObject, name)
                self.assertIsNotNone(child, name)
                prop = 'active' if name == 'commandPaletteLoader' else 'visible'
                child.setProperty(prop, True)
                self.app.processEvents()
                self.assertTrue(obj.property('overlayActive'), name)
                child.setProperty(prop, False)
                self.app.processEvents()
                self.assertFalse(obj.property('overlayActive'), name)
        finally:
            obj.deleteLater()
            self.app.processEvents()

    def test_tray_waits_for_process_exit(self):
        self.assertTrue(self.root.launch())
        self.wait_for_handoff()
        self.lib.simulation_make_window()
        self.root.adapterPoll()
        self.assertEqual(self.adapter.property('status'), 'attached')
        self.assertTrue(self.gate.request('tray'))
        self.assertEqual(self.adapter.property('status'), 'closing')
        self.assertEqual(self.approved.count(), 0)
        self.assertEqual(self.lib.simulation_close_messages(), 1)
        self.assertFalse(self.gate.request('quit'))
        self.lib.simulation_exit()
        self.gate.advance()
        self.assertEqual(self.approved.count(), 1)
        self.assertEqual(self.approved.at(0)[0], 'tray')
        self.assertFalse(self.adapter.property('processTracked'))

    def test_close_during_slow_launch_waits_for_handoff_and_exit(self):
        self.lib.simulation_block_reads()
        self.assertTrue(self.root.launch())
        self.wait_for_blocked_read()
        self.assertTrue(self.adapter.property('launchPending'))
        self.assertTrue(self.gate.request('tray'))
        self.assertTrue(self.gate.property('pending'))
        self.assertEqual(self.approved.count(), 0)
        self.assertEqual(self.adapter.property('status'), 'closing')
        self.lib.simulation_release_reads()
        self.wait_for_handoff()
        self.assertTrue(self.adapter.property('processTracked'))
        self.assertEqual(self.approved.count(), 0)
        self.lib.simulation_exit()
        self.gate.advance()
        self.assertEqual(self.approved.count(), 1)
        self.assertEqual(self.approved.at(0)[0], 'tray')

    def test_close_during_launch_closes_window_discovered_later(self):
        self.lib.simulation_block_reads()
        self.assertTrue(self.root.launch())
        self.wait_for_blocked_read()
        self.assertTrue(self.gate.request('quit'))
        self.lib.simulation_release_reads()
        self.wait_for_handoff()
        self.assertTrue(self.adapter.property('processTracked'))
        self.assertEqual(self.adapter.property('status'), 'closing')
        self.assertEqual(self.lib.simulation_close_messages(), 0)
        self.lib.simulation_make_window()
        self.gate.advance()
        self.assertEqual(self.lib.simulation_close_messages(), 1)
        self.assertEqual(self.lib.simulation_show(), 0)  # SW_HIDE
        self.assertEqual(self.approved.count(), 0)
        self.gate.advance()
        self.assertEqual(self.lib.simulation_close_messages(), 1)
        self.lib.simulation_exit()
        self.gate.advance()
        self.assertEqual(self.approved.count(), 1)
        self.assertEqual(self.approved.at(0)[0], 'quit')

    def test_cancel_during_slow_launch_keeps_tracking(self):
        self.lib.simulation_block_reads()
        self.assertTrue(self.root.launch())
        self.wait_for_blocked_read()
        self.assertTrue(self.gate.request('quit'))
        self.assertTrue(self.gate.keepOpen())
        self.assertEqual(self.cancelled.count(), 1)
        self.assertTrue(self.adapter.property('launchPending'))
        self.assertTrue(self.adapter.property('processTracked'))
        self.lib.simulation_release_reads()
        self.wait_for_handoff()
        self.assertTrue(self.adapter.property('processTracked'))
        self.assertEqual(self.approved.count(), 0)
        self.lib.simulation_exit()
        self.root.adapterPoll()
        self.assertFalse(self.adapter.property('processTracked'))

    def test_app_navigation_and_close_prompt_with_simulated_window(self):
        path = Path(__file__).parent / 'tests' / 'AppIntegrationHarness.qml'
        component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(path)))
        self.assertFalse(component.isError(), [e.toString() for e in component.errors()])
        window = component.create()
        self.assertIsNotNone(window, [e.toString() for e in component.errors()])
        try:
            integration = window.property('integrationObject')
            self.assertFalse(integration.property('available'))
            window.setProperty('sa6iCleanBackend', self.adapter)
            self.app.processEvents()
            self.assertTrue(integration.property('available'))
            integration.setProperty('testDirectory', '')
            self.assertFalse(integration.property('available'))
            integration.openClean()
            self.assertFalse(self.adapter.property('processTracked'))
            integration.setProperty('testDirectory', 'C:/test')
            self.assertTrue(integration.property('available'))
            window.setProperty('simulatedOverlayOpen', True)
            self.app.processEvents()
            integration.openClean()
            self.assertFalse(integration.property('cleanOpen'))
            self.assertFalse(self.adapter.property('processTracked'))
            window.setProperty('simulatedOverlayOpen', False)
            self.app.processEvents()
            # The entry opens an alternate layout in this same Qt window.
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(584, 24))
            self.assertTrue(integration.property('cleanOpen'))
            self.wait_for_handoff()
            self.lib.simulation_make_window()
            self.root.adapterPoll()
            QTest.qWait(120)
            self.assertEqual(self.adapter.property('status'), 'attached')
            self.assertEqual(self.lib.simulation_show(), 8)  # SW_SHOWNA
            # A modal overlay must be reachable and the child/layout hidden,
            # without dropping process ownership or changing navigation state.
            self.lib.simulation_set_fail_show(1)
            window.setProperty('simulatedOverlayOpen', True)
            self.app.processEvents()
            self.assertTrue(integration.property('cleanOpen'))
            self.assertFalse(integration.property('viewportReady'))
            self.assertTrue(integration.property('hideRequestFailed'))
            self.assertEqual(self.lib.simulation_show(), 8)  # hide was rejected
            self.assertTrue(self.adapter.property('processTracked'))
            self.lib.simulation_set_fail_show(0)
            integration.syncViewport()  # retry succeeds, but remains asynchronous on real Win32
            self.assertFalse(integration.property('hideRequestFailed'))
            self.assertEqual(self.lib.simulation_show(), 0)
            self.assertTrue(self.adapter.property('processTracked'))
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(400, 250))
            self.assertEqual(window.property('overlayClicks'), 1)
            window.setProperty('simulatedOverlayOpen', False)
            self.app.processEvents()
            self.assertTrue(integration.property('viewportReady'))
            self.assertEqual(self.lib.simulation_show(), 8)
            # Back hides the child without terminating the tracked process.
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(30, 76))
            self.assertFalse(integration.property('cleanOpen'))
            self.assertEqual(self.lib.simulation_show(), 0)  # SW_HIDE
            self.assertTrue(self.adapter.property('processTracked'))
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(584, 24))
            self.assertTrue(integration.property('cleanOpen'))
            self.assertEqual(self.lib.simulation_show(), 8)
            approved = QSignalSpy(integration.closeApproved)
            self.assertTrue(integration.requestClose('tray'))
            self.assertTrue(integration.property('closePending'))
            self.assertEqual(self.lib.simulation_show(), 0)
            window.setProperty('simulatedOverlayOpen', True)
            self.app.processEvents()
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(500, 165))
            self.assertFalse(integration.property('closePending'))
            self.assertEqual(approved.count(), 0)
            self.assertTrue(self.adapter.property('processTracked'))
            self.assertEqual(self.lib.simulation_show(), 0)
            window.setProperty('simulatedOverlayOpen', False)
            self.app.processEvents()
            self.assertEqual(self.lib.simulation_show(), 8)
            self.assertTrue(integration.requestClose('tray'))
            self.lib.simulation_exit()
            QTest.qWait(150)
            self.assertEqual(approved.count(), 1)
            self.assertEqual(approved.at(0)[0], 'tray')
            self.assertFalse(self.adapter.property('processTracked'))
        finally:
            window.setProperty('sa6iCleanBackend', None)
            window.close()
            window.deleteLater()
            self.app.processEvents()

    def test_app_cancel_during_launch_restores_selection(self):
        path = Path(__file__).parent / 'tests' / 'AppIntegrationHarness.qml'
        component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(path)))
        window = component.create()
        self.assertIsNotNone(window, [e.toString() for e in component.errors()])
        try:
            window.setProperty('sa6iCleanBackend', self.adapter)
            integration = window.property('integrationObject')
            self.lib.simulation_block_reads()
            integration.openClean()
            self.wait_for_blocked_read()
            self.assertTrue(integration.requestClose('tray'))
            self.assertTrue(integration.property('closePending'))
            QTest.qWait(50)  # allow the new prompt's anchors to settle
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(500, 165))
            self.assertFalse(integration.property('closePending'))
            self.assertTrue(self.adapter.property('launchPending'))
            self.lib.simulation_release_reads()
            self.wait_for_handoff()
            self.lib.simulation_make_window()
            self.root.adapterPoll()
            QTest.qWait(120)
            self.assertEqual(self.adapter.property('status'), 'attached')
            self.assertTrue(self.adapter.property('processTracked'))
            self.assertEqual(self.lib.simulation_show(), 8)  # SW_SHOWNA
            self.assertTrue(integration.property('viewportReady'))
        finally:
            self.lib.simulation_release_reads()
            self.wait_for_handoff()
            window.setProperty('sa6iCleanBackend', None)
            window.close()
            window.deleteLater()
            self.app.processEvents()

    def test_app_close_functions_through_integration_and_adapter(self):
        path = Path(__file__).parent / 'tests' / 'AppIntegrationHarness.qml'
        window_component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(path)))
        window = window_component.create()
        self.assertIsNotNone(window, [e.toString() for e in window_component.errors()])
        source = (Path(__file__).parents[2] / 'desktop/app/qml/App.qml').read_text(encoding='utf-8')
        start = source.index('    property int mainActivationEpoch:')
        end = source.index('\n    Component.onCompleted:', start)
        functions = source[start:end].replace('Preferences.closeToTray', 'mockPreferences.closeToTray')
        qml = '''import QtQuick
import QtQml
QtObject {
    id: app
    property var targetWindow: null
    property QtObject mockPreferences: QtObject { property bool closeToTray: true }
    property QtObject mainLoader: QtObject { property bool active: true; property var item: app.targetWindow }
    property Timer trayTrimTimer: Timer { interval: 100000 }
''' + functions + '\n}'
        app_component = QQmlComponent(self.engine)
        app_component.setData(qml.encode('utf-8'), QUrl())
        coordinator = app_component.create()
        self.assertIsNotNone(coordinator, [e.toString() for e in app_component.errors()])
        try:
            window.setProperty('sa6iCleanBackend', self.adapter)
            coordinator.setProperty('targetWindow', window)
            window.sa6iCloseApproved.connect(coordinator.finishMainClose)
            integration = window.property('integrationObject')
            integration.openClean()
            self.wait_for_handoff()
            self.lib.simulation_make_window()
            self.root.adapterPoll()
            self.assertEqual(self.adapter.property('status'), 'attached')
            coordinator.onMainClosed()
            self.assertTrue(integration.property('closePending'))
            self.assertEqual(self.lib.simulation_close_messages(), 1)
            self.assertTrue(coordinator.property('mainLoader').property('active'))
            self.assertEqual(window.property('teardownCount'), 0)
            self.lib.simulation_exit()
            QTest.qWait(180)
            self.assertFalse(self.adapter.property('processTracked'))
            self.assertEqual(window.property('savedCount'), 1)
            self.assertEqual(window.property('teardownCount'), 1)
            self.assertFalse(coordinator.property('mainLoader').property('active'))
        finally:
            coordinator.setProperty('targetWindow', None)
            window.setProperty('sa6iCleanBackend', None)
            window.close()
            coordinator.deleteLater()
            window.deleteLater()
            self.app.processEvents()

    def _make_coordinator_window(self):
        path = Path(__file__).parent / 'tests' / 'AppIntegrationHarness.qml'
        window_component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(path)))
        window = window_component.create()
        self.assertIsNotNone(window, [e.toString() for e in window_component.errors()])
        source = (Path(__file__).parents[2] / 'desktop/app/qml/App.qml').read_text(encoding='utf-8')
        start = source.index('    property int mainActivationEpoch:')
        end = source.index('\n    Component.onCompleted:', start)
        functions = source[start:end].replace('Preferences.closeToTray', 'mockPreferences.closeToTray')
        qml = '''import QtQuick
import QtQml
QtObject {
    id: app
    property var targetWindow: null
    property QtObject mockPreferences: QtObject { property bool closeToTray: true }
    property QtObject mainLoader: QtObject { property bool active: true; property var item: app.targetWindow }
    property Timer trayTrimTimer: Timer { interval: 100000 }
''' + functions + '\n}'
        app_component = QQmlComponent(self.engine)
        app_component.setData(qml.encode('utf-8'), QUrl())
        coordinator = app_component.create()
        self.assertIsNotNone(coordinator, [e.toString() for e in app_component.errors()])
        hook = BindAdapterHook(self.lib, self.address)
        window.setProperty('bindBackendHook', hook)
        window.setProperty('sa6iCleanBackend', self.adapter)
        coordinator.setProperty('targetWindow', window)
        window.sa6iCloseApproved.connect(coordinator.finishMainClose)
        return window, coordinator, hook, window_component, app_component

    def _cleanup_coordinator_window(self, window, coordinator):
        self.lib.simulation_release_reads()
        self.wait_for_handoff()
        coordinator.setProperty('targetWindow', None)
        window.setProperty('bindBackendHook', None)
        window.setProperty('sa6iCleanBackend', None)
        window.close()
        coordinator.deleteLater()
        window.deleteLater()
        self.app.processEvents()

    def test_reactivate_pending_tray_through_real_adapter(self):
        window, coordinator, hook, window_component, app_component = self._make_coordinator_window()
        try:
            integration = window.property('integrationObject')
            integration.openClean()
            self.wait_for_handoff()
            self.lib.simulation_make_window()
            self.root.adapterPoll()
            self.assertEqual(self.adapter.property('status'), 'attached')
            coordinator.onMainClosed()
            self.assertTrue(integration.property('closePending'))
            self.assertEqual(self.lib.simulation_close_messages(), 1)
            coordinator.showMain()
            self.assertFalse(integration.property('closePending'))
            self.assertEqual(self.adapter.property('status'), 'attached')
            self.assertTrue(self.adapter.property('processTracked'))
            # The posted close may still complete after cancellation.
            self.lib.simulation_exit()
            self.root.adapterPoll()
            QTest.qWait(150)
            self.assertFalse(self.adapter.property('processTracked'))
            self.assertEqual(window.property('teardownCount'), 0)
            self.assertTrue(coordinator.property('mainLoader').property('active'))
        finally:
            self._cleanup_coordinator_window(window, coordinator)

    def test_reactivate_during_blocked_launch_through_real_adapter(self):
        window, coordinator, hook, window_component, app_component = self._make_coordinator_window()
        try:
            integration = window.property('integrationObject')
            self.lib.simulation_block_reads()
            integration.openClean()
            self.wait_for_blocked_read()
            coordinator.onMainClosed()
            self.assertTrue(integration.property('closePending'))
            self.assertEqual(self.adapter.property('status'), 'closing')
            coordinator.showMain()
            self.assertFalse(integration.property('closePending'))
            self.assertEqual(self.adapter.property('status'), 'launching')
            self.assertTrue(self.adapter.property('processTracked'))
            self.lib.simulation_release_reads()
            self.wait_for_handoff()
            self.lib.simulation_make_window()
            self.root.adapterPoll()
            QTest.qWait(120)
            self.assertEqual(self.adapter.property('status'), 'attached')
            self.assertEqual(self.lib.simulation_show(), 8)  # SW_SHOWNA
            self.assertTrue(integration.property('viewportReady'))
            self.assertEqual(window.property('teardownCount'), 0)
        finally:
            self._cleanup_coordinator_window(window, coordinator)

    def test_reactivation_does_not_cancel_quit_through_real_adapter(self):
        window, coordinator, hook, window_component, app_component = self._make_coordinator_window()
        try:
            integration = window.property('integrationObject')
            integration.openClean()
            self.wait_for_handoff()
            self.lib.simulation_make_window()
            self.root.adapterPoll()
            self.assertTrue(integration.requestClose('quit'))
            self.assertTrue(integration.property('closePending'))
            coordinator.showMain()
            self.assertTrue(integration.property('closePending'))
            self.assertEqual(self.adapter.property('status'), 'closing')
            self.assertTrue(self.adapter.property('processTracked'))
        finally:
            # Avoid executing the quit branch, which expects the real controller.
            window.sa6iCloseApproved.disconnect(coordinator.finishMainClose)
            self._cleanup_coordinator_window(window, coordinator)

    def test_reactivate_after_approval_rebinds_real_adapter(self):
        window, coordinator, hook, window_component, app_component = self._make_coordinator_window()
        try:
            integration = window.property('integrationObject')
            integration.openClean()
            self.wait_for_handoff()
            first_profile = self.adapter.property('testProfile')
            self.lib.simulation_make_window()
            self.root.adapterPoll()
            self.assertEqual(self.adapter.property('status'), 'attached')
            # Direct signal callbacks run in order: approval queues teardown,
            # then this activation arrives before the deferred callback.
            window.sa6iCloseApproved.connect(lambda action: coordinator.showMain())
            coordinator.onMainClosed()
            self.assertTrue(integration.property('closePending'))
            self.lib.simulation_exit()
            self.root.adapterPoll()
            QTest.qWait(180)
            self.assertEqual(self.adapter.property('status'), 'closed')
            self.assertFalse(self.adapter.property('processTracked'))
            self.assertFalse(integration.property('shuttingDown'))
            self.assertFalse(integration.property('cleanOpen'))
            self.assertTrue(coordinator.property('mainLoader').property('active'))
            self.assertEqual(window.property('teardownCount'), 0)
            integration.openClean()  # Rebind to the same simulated parent.
            self.wait_for_handoff()
            self.assertTrue(integration.property('cleanOpen'))
            self.assertTrue(self.adapter.property('processTracked'))
            self.assertEqual(self.lib.simulation_starts(), 2)
            self.assertNotEqual(self.adapter.property('testProfile'), first_profile)
        finally:
            self._cleanup_coordinator_window(window, coordinator)

    def test_immediate_second_tray_close_through_real_adapter(self):
        window, coordinator, hook, window_component, app_component = self._make_coordinator_window()
        try:
            integration = window.property('integrationObject')
            integration.openClean()
            self.wait_for_handoff()
            self.lib.simulation_make_window()
            self.root.adapterPoll()
            activations = []

            def reactivate_and_close_again(action):
                if not activations:
                    activations.append(action)
                    coordinator.showMain()
                    coordinator.onMainClosed()

            window.sa6iCloseApproved.connect(reactivate_and_close_again)
            coordinator.onMainClosed()
            self.lib.simulation_exit()
            self.root.adapterPoll()
            QTest.qWait(350)
            self.assertEqual(activations, ['tray'])
            self.assertFalse(self.adapter.property('processTracked'))
            self.assertFalse(coordinator.property('mainLoader').property('active'))
            self.assertEqual(window.property('teardownCount'), 1)
        finally:
            self._cleanup_coordinator_window(window, coordinator)

    def test_overlay_during_launch_keeps_late_child_hidden(self):
        path = Path(__file__).parent / 'tests' / 'AppIntegrationHarness.qml'
        component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(path)))
        self.assertFalse(component.isError(), [e.toString() for e in component.errors()])
        window = component.create()
        self.assertIsNotNone(window, [e.toString() for e in component.errors()])
        try:
            window.setProperty('sa6iCleanBackend', self.adapter)
            integration = window.property('integrationObject')
            self.lib.simulation_block_reads()
            integration.openClean()
            self.wait_for_blocked_read()
            window.setProperty('simulatedOverlayOpen', True)
            self.app.processEvents()
            self.lib.simulation_release_reads()
            self.wait_for_handoff()
            self.lib.simulation_make_window()
            self.root.adapterPoll()
            self.assertEqual(self.adapter.property('status'), 'attached')
            self.assertEqual(self.lib.simulation_show(), 0)  # SW_HIDE
            self.assertTrue(self.adapter.property('processTracked'))
            self.assertFalse(integration.property('viewportReady'))
            window.setProperty('simulatedOverlayOpen', False)
            self.app.processEvents()
            self.assertEqual(self.lib.simulation_show(), 8)  # SW_SHOWNA
        finally:
            self.lib.simulation_release_reads()
            self.wait_for_handoff()
            window.setProperty('sa6iCleanBackend', None)
            window.close()
            window.deleteLater()
            self.app.processEvents()

    def test_cancel_keeps_tracking_until_later_exit(self):
        self.assertTrue(self.root.launch())
        self.wait_for_handoff()
        self.lib.simulation_make_window()
        self.root.adapterPoll()
        self.assertTrue(self.gate.request('quit'))
        self.assertTrue(self.gate.keepOpen())
        self.assertEqual(self.cancelled.count(), 1)
        self.assertEqual(self.approved.count(), 0)
        self.assertTrue(self.adapter.property('processTracked'))
        self.assertEqual(self.adapter.property('status'), 'attached')
        self.lib.simulation_exit()
        self.root.adapterPoll()
        self.assertFalse(self.adapter.property('processTracked'))
        self.assertEqual(self.adapter.property('status'), 'idle')
        self.assertEqual(self.approved.count(), 0)


if __name__ == '__main__':
    unittest.main()
