// SPDX-License-Identifier: GPL-3.0-or-later
//! Read-only local checks. Never invokes a repair or a shell command.
#![allow(unsafe_code)]
use serde::Serialize;

#[derive(Serialize)]
struct Finding {
    title: &'static str,
    status: &'static str,
    detail: String,
}

fn disk_finding(free: Option<u64>) -> Finding {
    match free {
        Some(bytes) if bytes < 5 * 1024 * 1024 * 1024 => Finding {
            title: "Windows drive space",
            status: "attention",
            detail: format!(
                "{:.1} GiB available. Less than 5 GiB is a reason to review free space; this does not establish why the PC is slow. Don't delete files without reviewing them.",
                bytes as f64 / 1_073_741_824.0
            ),
        },
        Some(bytes) => Finding {
            title: "Windows drive space",
            status: "ok",
            detail: format!(
                "{:.1} GiB available. This check alone cannot establish overall system health.",
                bytes as f64 / 1_073_741_824.0
            ),
        },
        None => Finding {
            title: "Windows drive space",
            status: "unknown",
            detail: "Could not read the available space on the Windows drive.".into(),
        },
    }
}

#[cfg(target_os = "windows")]
fn disk_free() -> Option<u64> {
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetWindowsDirectoryW(buffer: *mut u16, size: u32) -> u32;
        fn GetDiskFreeSpaceExW(path: *const u16, available: *mut u64, total: *mut u64, free: *mut u64)
        -> i32;
    }
    let mut path = [0u16; 32768];
    // Windows directory path is used directly, not an environment variable or user input.
    let n = unsafe { GetWindowsDirectoryW(path.as_mut_ptr(), path.len() as u32) } as usize;
    if n == 0 || n >= path.len() {
        return None;
    }
    path[n] = 0;
    let mut available = 0u64;
    let ok = unsafe {
        GetDiskFreeSpaceExW(path.as_ptr(), &mut available, std::ptr::null_mut(), std::ptr::null_mut())
    };
    if ok == 0 { None } else { Some(available) }
}
#[cfg(not(target_os = "windows"))]
fn disk_free() -> Option<u64> {
    None
}

#[cfg(target_os = "windows")]
fn network_finding() -> Finding {
    match crate::win::doctor::has_connected_network() {
        Ok(true) => Finding {
            title: "Network connection", status: "ok",
            detail: "Windows reports a connected network. This does not confirm internet access; VPNs and virtual networks can affect the result.".into(),
        },
        Ok(false) => Finding { title: "Network connection", status: "attention", detail: "Windows reports no connected network. Check Wi-Fi or the network cable. This is not a complete internet diagnosis.".into() },
        Err(_) => Finding { title: "Network connection", status: "unknown", detail: "Windows could not report the network status. No conclusion can be drawn.".into() },
    }
}
#[cfg(not(target_os = "windows"))]
fn network_finding() -> Finding {
    Finding {
        title: "Network connection",
        status: "unknown",
        detail: "This check is only implemented on Windows.".into(),
    }
}

pub fn scan_json() -> String {
    let findings = [network_finding(), disk_finding(disk_free()), Finding {
        title: "Internet access", status: "not tested",
        detail: "This local scan makes no internet requests. Connected to a network does not mean the internet is working.".into(),
    }];
    serde_json::to_string(&findings).unwrap_or_else(|_| "[]".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn free_space_boundaries_and_unknown() {
        assert_eq!(disk_finding(None).status, "unknown");
        assert_eq!(disk_finding(Some(0)).status, "attention");
        assert_eq!(disk_finding(Some(5 * 1024 * 1024 * 1024 - 1)).status, "attention");
        assert_eq!(disk_finding(Some(5 * 1024 * 1024 * 1024)).status, "ok");
    }
}
