"""Exercise selected real updater functions in a Rust harness with stubbed IO.

Set SA6I_TEST_RUSTC. This compiles extracted source functions, not the app;
the stubs return before any filesystem, network or installer action. Both
ordinary and experimental cfgs are tested on the host OS, not on Windows.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUSTC = os.environ.get('SA6I_TEST_RUSTC')


def function(source, signature):
    start = source.index(signature)
    # These top-level functions close at the beginning of a line.
    end = source.index('\n}', start) + 2
    return source[start:end]


@unittest.skipUnless(RUSTC, 'set SA6I_TEST_RUSTC to a Rust compiler')
class UpdaterGuardHarness(unittest.TestCase):
    def test_selected_actual_functions_in_both_build_modes(self):
        source = (ROOT / 'desktop/app/src/updater.rs').read_text(encoding='utf-8')
        functions = '\n\n'.join(function(source, name) for name in (
            'pub fn available()', 'pub fn set_channel(', 'pub fn check_soon()',
            'pub fn can_update()', 'pub fn stage(',
        ))
        harness = r'''
#![allow(dead_code)]
use std::{path::{Path, PathBuf}, sync::{Mutex, MutexGuard, Condvar, atomic::{AtomicUsize, Ordering}}};
#[derive(Clone)]
pub struct Update { installer_name: String, installer_url: String }
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Channel { Stable }
#[derive(Debug, PartialEq, Eq)]
pub enum StageError { Disabled, Network(String), Damaged, Disk(String) }
static FOUND: Mutex<Option<Update>> = Mutex::new(None);
static CHANNEL: Mutex<Option<Channel>> = Mutex::new(None);
static SOON: (Mutex<bool>, Condvar) = (Mutex::new(false), Condvar::new());
static WRITES: AtomicUsize = AtomicUsize::new(0);
static HASHES: AtomicUsize = AtomicUsize::new(0);
const MAX_INSTALLER: u64 = 400;
fn found() -> MutexGuard<'static, Option<Update>> { FOUND.lock().unwrap() }
fn write_service_channel(_: Channel) { WRITES.fetch_add(1, Ordering::SeqCst); }
fn expected_hash(_: &Update) -> Result<String, StageError> {
    HASHES.fetch_add(1, Ordering::SeqCst); Err(StageError::Damaged)
}
fn staging_dir() -> PathBuf { panic!("unexpected staging directory access") }
fn sha256_file(_: &Path) -> std::io::Result<String> { panic!("unexpected file read") }
#[cfg(target_os = "linux")]
fn current_euid() -> u32 { panic!("unexpected uid lookup") }
mod http {
    use std::path::Path;
    pub fn download(_: &str, _: &Path, _: u64, _: impl FnMut(u64, u64)) -> Result<(), String> {
        panic!("unexpected network access")
    }
}
mod autostart {
    use std::path::Path;
    pub fn is_installed(_: &Path) -> bool { true }
}
''' + functions + r'''
fn main() {
    let test_update = Update { installer_name: "test".into(), installer_url: "test".into() };
    *found() = Some(test_update.clone());
    let experimental = cfg!(sa6i_clean_experiment);
    assert_eq!(available().is_some(), !experimental);
    assert_eq!(can_update(), !experimental);
    set_channel(Channel::Stable);
    assert_eq!(WRITES.load(Ordering::SeqCst), usize::from(!experimental));
    assert_eq!(*SOON.0.lock().unwrap(), !experimental);
    let result = stage(&test_update, |_, _| panic!("unexpected progress callback"));
    if experimental {
        assert_eq!(result, Err(StageError::Disabled));
        assert_eq!(HASHES.load(Ordering::SeqCst), 0);
    } else {
        assert_eq!(result, Err(StageError::Damaged));
        assert_eq!(HASHES.load(Ordering::SeqCst), 1);
    }
}
'''
        with tempfile.TemporaryDirectory(prefix='sa6i-updater-') as temp:
            temp = Path(temp)
            rust_file = temp / 'updater.rs'
            rust_file.write_text(harness, encoding='utf-8')
            for experimental in (False, True):
                binary = temp / ('experiment' if experimental else 'ordinary')
                if os.name == 'nt':
                    binary = binary.with_suffix('.exe')
                args = [RUSTC, '--edition=2024', '-Dwarnings', '--check-cfg', 'cfg(sa6i_clean_experiment)']
                if experimental:
                    args.extend(['--cfg', 'sa6i_clean_experiment'])
                subprocess.run([*args, str(rust_file), '-o', str(binary)], check=True, timeout=60)
                subprocess.run([str(binary)], check=True, timeout=30)


if __name__ == '__main__':
    unittest.main()
