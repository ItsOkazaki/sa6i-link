// SPDX-License-Identifier: GPL-3.0-or-later
//! Host adapter for the UI-independent read-only DZFix core.
use dzfix_core::{Reading, UnavailableReason};

pub fn scan_json() -> String {
    #[cfg(target_os = "windows")]
    {
        let network = match crate::win::doctor::has_connected_network() {
            Ok(value) => Reading::Available { value },
            Err(_) => Reading::Unavailable { reason: UnavailableReason::Error },
        };
        match dzfix_core::windows::collect(std::time::Duration::from_secs(10), network) {
            Ok(snapshot) => serde_json::to_string(&snapshot)
                .unwrap_or_else(|_| r#"{"error":"The result could not be displayed."}"#.into()),
            Err(_) => r#"{"error":"The scan could not be completed."}"#.into(),
        }
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _unused: Reading<bool> = Reading::Unavailable { reason: UnavailableReason::Unsupported };
        r#"{"error":"This preview is currently implemented on Windows only."}"#.into()
    }
}
