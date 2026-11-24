"""Compile real Windows tray hotkey entry points against isolated OS stubs.

This tests control flow in both build modes, not Windows APIs or the full app.
Requires SA6I_TEST_RUSTC to point to a working Rust compiler.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUSTC = os.environ.get('SA6I_TEST_RUSTC')


@unittest.skipUnless(RUSTC, 'set SA6I_TEST_RUSTC to a Rust compiler')
class HotkeyGuardHarness(unittest.TestCase):
    def test_actual_registration_and_update_in_both_modes(self):
        source = (ROOT / 'desktop/app/src/win/tray.rs').read_text(encoding='utf-8')
        start = source.index('pub fn update_hotkeys(')
        end = source.index('\n/// The tray icon.', start)
        real_functions = source[start:end]
        harness = r'''
#![allow(non_snake_case, non_camel_case_types, dead_code, unused_variables, unused_unsafe)]
use std::sync::{Mutex, atomic::{AtomicIsize, AtomicUsize, Ordering}};
extern crate self as tracing;
#[macro_export] macro_rules! debug { ($($tt:tt)*) => {}; }
static HOTKEY_SPECS: Mutex<(String,String,String,String)> = Mutex::new((String::new(),String::new(),String::new(),String::new()));
static TRAY_HWND: AtomicIsize = AtomicIsize::new(1);
static POSTS: AtomicUsize = AtomicUsize::new(0);
static REGISTERS: AtomicUsize = AtomicUsize::new(0);
static UNREGISTERS: AtomicUsize = AtomicUsize::new(0);
#[derive(Clone, Copy)] struct HWND(*mut std::ffi::c_void);
struct WPARAM(usize); struct LPARAM(isize); struct HOT_KEY_MODIFIERS(u32);
const WM_UPDATE_HOTKEYS: u32 = 1;
const HOTKEY_PHOTO_ID: i32 = 1; const HOTKEY_SCAN_ID: i32 = 2;
const HOTKEY_PALETTE_ID: i32 = 3; const HOTKEY_SHELF_ID: i32 = 4;
fn parse_hotkey(s: &str) -> Option<(u32,u32)> { if s.is_empty() {None} else {Some((1,2))} }
fn PostMessageW(_: Option<HWND>, _: u32, _: WPARAM, _: LPARAM) -> Result<(),()> { POSTS.fetch_add(1,Ordering::SeqCst); Ok(()) }
fn RegisterHotKey(_: Option<HWND>, _: i32, _: HOT_KEY_MODIFIERS, _: u32) -> Result<(),()> { REGISTERS.fetch_add(1,Ordering::SeqCst); Ok(()) }
fn UnregisterHotKey(_: Option<HWND>, _: i32) -> Result<(),()> { UNREGISTERS.fetch_add(1,Ordering::SeqCst); Ok(()) }
''' + real_functions + r'''
fn main() {
    // Startup path calls apply directly before any update. Preferences can
    // call update even after the tray exists; exercise both paths.
    unsafe { apply_hotkeys_on_window(HWND(std::ptr::null_mut())) };
    update_hotkeys("A", "B", "C", "D");
    unsafe { apply_hotkeys_on_window(HWND(std::ptr::null_mut())) };
    if cfg!(sa6i_clean_experiment) {
        assert_eq!(POSTS.load(Ordering::SeqCst), 0);
        assert_eq!(REGISTERS.load(Ordering::SeqCst), 0);
        assert_eq!(UNREGISTERS.load(Ordering::SeqCst), 0);
        assert!(HOTKEY_SPECS.lock().unwrap().0.is_empty());
    } else {
        assert_eq!(POSTS.load(Ordering::SeqCst), 1);
        assert_eq!(REGISTERS.load(Ordering::SeqCst), 4);
        assert_eq!(UNREGISTERS.load(Ordering::SeqCst), 8);
        assert_eq!(HOTKEY_SPECS.lock().unwrap().0, "A");
    }
}
'''
        with tempfile.TemporaryDirectory(prefix='sa6i-hotkeys-') as directory:
            directory = Path(directory)
            rust_file = directory / 'guard.rs'
            rust_file.write_text(harness, encoding='utf-8')
            for experiment in (False, True):
                binary = directory / ('experiment' if experiment else 'ordinary')
                command = [RUSTC, '--edition=2024', '-Dwarnings', str(rust_file), '-o', str(binary)]
                if experiment:
                    command.extend(['--cfg', 'sa6i_clean_experiment'])
                subprocess.run(command, check=True, timeout=60)
                subprocess.run([str(binary)], check=True, timeout=30)


if __name__ == '__main__':
    unittest.main()
