"""Structural regression checks for experimental build guards.

These inspect source text, not compiled Rust or Windows behavior. Run the Rust
unit tests and a full Windows build separately before trusting the experiment.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
BUILD = (ROOT / 'desktop/app/build.rs').read_text(encoding='utf-8')
MAIN = (ROOT / 'desktop/app/src/main.rs').read_text(encoding='utf-8')
UPDATER = (ROOT / 'desktop/app/src/updater.rs').read_text(encoding='utf-8')
TOAST = (ROOT / 'desktop/app/src/win/toast.rs').read_text(encoding='utf-8')
JUMPLIST = (ROOT / 'desktop/app/src/win/jumplist.rs').read_text(encoding='utf-8')
STORAGE = (ROOT / 'desktop/app/src/storage.rs').read_text(encoding='utf-8')
TRAY = (ROOT / 'desktop/app/src/win/tray.rs').read_text(encoding='utf-8')


def body_between(text, start, end):
    start_pos = text.index(start)
    return text[start_pos:text.index(end, start_pos)]


class ExperimentalGuardStructure(unittest.TestCase):
    def test_one_windows_build_decision_controls_rust_and_cpp(self):
        section = body_between(BUILD, 'let clean_experiment =', 'let mut builder =')
        self.assertIn('CARGO_CFG_TARGET_OS', section)
        self.assertIn('Ok("windows")', section)
        self.assertIn('SA6I_CLEAN_EXPERIMENT', section)
        self.assertIn('Ok("1")', section)
        self.assertIn('if clean_experiment', section)
        self.assertIn('cargo::rustc-cfg=sa6i_clean_experiment', section)
        self.assertIn('u8::from(clean_experiment)', section)

    def test_entry_policy_precedes_setup_service_and_data_creation(self):
        section = body_between(MAIN, 'fn main() -> ExitCode {', 'let share_payload =')
        gate = section.index('if cfg!(sa6i_clean_experiment)')
        for action in ('run_setup_window(', 'updater::run_service()', 'uninstall()',
                       'std::fs::create_dir_all(&data_dir)'):
            self.assertLess(gate, section.index(action), action)
        policy = body_between(MAIN, 'fn validate_clean_experiment_options(', '\nfn main()')
        for flag in ('options.setup.is_some()', 'options.remove', 'options.uninstall',
                     'options.update_service', 'options.updated', 'options.register_vcam',
                     'options.unregister_vcam', 'options.widget_provider', 'path.is_absolute()'):
            self.assertIn(flag, policy)

    def test_shared_windows_integrations_are_guarded_at_entry(self):
        for text, start, end, action in (
            (TOAST, 'pub fn set_process_id()', 'pub fn start(', 'SetCurrentProcessExplicitAppUserModelID'),
            (TOAST, 'pub fn start(', 'fn send(', 'std::thread::Builder'),
            (TOAST, 'pub fn unregister()', 'fn register(', 'ToastNotificationManager::History()'),
            (JUMPLIST, 'pub fn register(', 'fn try_register(', 'try_register('),
            (JUMPLIST, 'pub fn unregister()', '#[cfg(test)]', 'with_com('),
            (TRAY, 'pub fn update_hotkeys(', 'unsafe fn apply_hotkeys_on_window(', 'HOTKEY_SPECS.lock()'),
            (TRAY, 'unsafe fn apply_hotkeys_on_window(', '/// The tray icon.', 'UnregisterHotKey('),
            (STORAGE, '    pub fn start() {', '    pub fn sync() {', 'let mut map = active_roots()'),
            (STORAGE, '    pub fn sync() {', '    pub fn on_event(', 'core_host::host()'),
            (STORAGE, '    pub fn on_event(', '    pub fn shutdown()', 'match event'),
            (STORAGE, '    pub fn unregister_all()', '    pub fn sync_root_path_for(', 'shutdown()'),
        ):
            with self.subTest(function=start, action=action):
                section = body_between(text, start, end)
                prefix = section[:section.index(action)]
                self.assertIn('if cfg!(sa6i_clean_experiment)', prefix)
                self.assertRegex(prefix, r'\breturn\s*;')

    def test_update_guards_precede_io_and_process_creation(self):
        for start, end, dangerous in (
            ('pub fn available()', 'pub fn channel()', 'found().clone()'),
            ('pub fn set_channel(', 'fn service_channel_file()', 'write_service_channel(channel)'),
            ('pub fn check_soon()', 'fn wait_for_soon(', 'wake.notify_all()'),
            ('pub fn check_now(', 'fn announce(', 'latest()'),
            ('pub fn install(', 'pub enum StageError', 'stage(&update'),
            ('pub fn stage(', 'fn install_with_task(', 'expected_hash(update)'),
            ('fn install_with_task(', 'fn spawn_relauncher(', 'spawn_relauncher('),
            ('pub fn run_service()', 'fn unix_seconds_now()', 'OpenOptions::new()'),
            ('fn install_with_prompt(update:', 'const PRIVILEGED_DEB_INSTALL_SCRIPT', 'expected_hash(update)'),
        ):
            with self.subTest(function=start):
                section = body_between(UPDATER, start, end)
                self.assertLess(section.index('if cfg!(sa6i_clean_experiment)'), section.index(dangerous))
                self.assertRegex(section[:section.index(dangerous)], r'\breturn(?:\s|;)')
        can_update = body_between(UPDATER, 'pub fn can_update()', 'pub fn start()')
        self.assertIn('!cfg!(sa6i_clean_experiment)', can_update)
        start = body_between(UPDATER, 'pub fn start()', 'pub fn check_now(')
        self.assertLess(start.index('if !can_update()'), start.index('std::thread::Builder'))


if __name__ == '__main__':
    unittest.main()
