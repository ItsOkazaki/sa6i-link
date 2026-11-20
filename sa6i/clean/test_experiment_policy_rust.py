"""Compile the actual standalone options validator with a minimal Options stub.

Requires SA6I_TEST_RUSTC; this is not a full Cargo build or a Windows test.
The harness does not exercise argument parsing, Qt, or the updater.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUSTC = os.environ.get('SA6I_TEST_RUSTC')


@unittest.skipUnless(RUSTC, 'set SA6I_TEST_RUSTC to a Rust compiler')
class ExperimentOptionsPolicy(unittest.TestCase):
    def test_actual_validator_with_stubbed_options(self):
        source = (ROOT / 'desktop/app/src/main.rs').read_text(encoding='utf-8')
        start = source.index('fn validate_clean_experiment_options(')
        end = source.index('\nfn main() -> ExitCode', start)
        validator = source[start:end]
        harness = r'''
use std::path::PathBuf;
#[derive(Default)]
struct Options {
    data_dir: Option<PathBuf>, setup: Option<PathBuf>, remove: bool,
    uninstall: bool, update_service: bool, updated: bool,
    register_vcam: bool, unregister_vcam: bool, widget_provider: bool,
}
''' + validator + r'''
fn main() {
    let mut opts = Options::default();
    assert!(validate_clean_experiment_options(&opts).is_err());
    opts.data_dir = Some(PathBuf::from("relative"));
    assert!(validate_clean_experiment_options(&opts).is_err());
    opts.data_dir = Some(std::env::current_dir().unwrap());
    assert!(validate_clean_experiment_options(&opts).is_ok());
    opts.setup = Some(PathBuf::new());
    assert!(validate_clean_experiment_options(&opts).is_err());
    opts.setup = None;
    macro_rules! rejected { ($field:ident) => {
        opts.$field = true;
        assert!(validate_clean_experiment_options(&opts).is_err(), stringify!($field));
        opts.$field = false;
    }}
    rejected!(remove); rejected!(uninstall); rejected!(update_service);
    rejected!(updated); rejected!(register_vcam); rejected!(unregister_vcam);
    rejected!(widget_provider);
    assert!(validate_clean_experiment_options(&opts).is_ok());
}
'''
        with tempfile.TemporaryDirectory(prefix='sa6i-policy-') as directory:
            directory = Path(directory)
            rust_file = directory / 'policy.rs'
            rust_file.write_text(harness, encoding='utf-8')
            binary = directory / ('policy.exe' if os.name == 'nt' else 'policy')
            subprocess.run([RUSTC, '--edition=2024', '-Dwarnings', str(rust_file), '-o', str(binary)],
                           check=True, timeout=60)
            subprocess.run([str(binary)], check=True, timeout=30)


if __name__ == '__main__':
    unittest.main()
