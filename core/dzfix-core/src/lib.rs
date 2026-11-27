// SPDX-License-Identifier: GPL-3.0-or-later
//! DZFix's host-independent, read-only evidence model and calculations.
//! This crate cannot perform repairs, execute commands or contact a network.
#![deny(unsafe_code)]
use serde::{Deserialize, Serialize};

/// A value is never substituted with zero when a collector fails.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum Reading<T> {
    Available { value: T },
    Unavailable { reason: UnavailableReason },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum UnavailableReason {
    Unsupported,
    Error,
    InvalidData,
    InsufficientSamples,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct CpuTimes {
    pub idle: u64,
    pub kernel: u64,
    pub user: u64,
}

/// GetSystemTimes kernel time includes idle. Inputs are cumulative 100 ns units.
/// Result is percent of aggregate CPU time, *not* divided by logical CPU count.
pub fn cpu_percent(before: CpuTimes, after: CpuTimes) -> Reading<f64> {
    let delta = || -> Option<f64> {
        let idle = after.idle.checked_sub(before.idle)?;
        let kernel = after.kernel.checked_sub(before.kernel)?;
        let user = after.user.checked_sub(before.user)?;
        let total = kernel.checked_add(user)?;
        if total == 0 || idle > kernel || idle > total {
            return None;
        }
        Some(100.0 * (total - idle) as f64 / total as f64)
    };
    match delta() {
        Some(value) => Reading::Available { value },
        None => Reading::Unavailable { reason: UnavailableReason::InvalidData },
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct MemoryBytes {
    pub total: u64,
    pub available: u64,
}

pub fn validate_memory(total: u64, available: u64) -> Reading<MemoryBytes> {
    if total == 0 || available > total {
        Reading::Unavailable { reason: UnavailableReason::InvalidData }
    } else {
        Reading::Available { value: MemoryBytes { total, available } }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct DriveBytes {
    pub total: u64,
    pub available_to_user: u64,
}

pub fn validate_drive(total: u64, available_to_user: u64) -> Reading<DriveBytes> {
    if total == 0 || available_to_user > total {
        Reading::Unavailable { reason: UnavailableReason::InvalidData }
    } else {
        Reading::Available { value: DriveBytes { total, available_to_user } }
    }
}

/// Host-provided evidence, not a diagnosis or a score. Times are Unix epoch ms.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Snapshot {
    pub schema_version: u32,
    pub captured_unix_ms: u64,
    pub cpu_interval_ms: u64,
    pub cpu_percent: Reading<f64>,
    pub memory: Reading<MemoryBytes>,
    pub windows_drive: Reading<DriveBytes>,
    pub network_connected: Reading<bool>,
}

impl Snapshot {
    pub const SCHEMA_VERSION: u32 = 1;
}

#[cfg(test)]
mod tests {
    use super::*;
    fn times(idle: u64, kernel: u64, user: u64) -> CpuTimes {
        CpuTimes { idle, kernel, user }
    }
    #[test]
    fn cpu_normal_and_idle_are_calculated_once() {
        assert_eq!(cpu_percent(times(0, 0, 0), times(20, 60, 40)), Reading::Available { value: 80.0 });
        assert_eq!(cpu_percent(times(10, 20, 10), times(110, 120, 10)), Reading::Available { value: 0.0 });
        assert_eq!(cpu_percent(times(10, 20, 10), times(10, 70, 60)), Reading::Available { value: 100.0 });
    }
    #[test]
    fn cpu_unavailable_for_resets_and_impossible_data() {
        let bad = Reading::Unavailable { reason: UnavailableReason::InvalidData };
        assert_eq!(cpu_percent(times(1, 1, 1), times(1, 1, 1)), bad);
        assert_eq!(cpu_percent(times(5, 5, 5), times(1, 6, 6)), bad);
        assert_eq!(cpu_percent(times(0, 0, 0), times(20, 10, 50)), bad);
        assert_eq!(cpu_percent(times(0, 0, 0), times(0, u64::MAX, 1)), bad);
    }
    #[test]
    fn memory_and_disk_validate_without_confusing_zero_and_unknown() {
        assert!(matches!(validate_memory(0, 0), Reading::Unavailable { .. }));
        assert!(matches!(validate_memory(100, 101), Reading::Unavailable { .. }));
        assert_eq!(
            validate_memory(100, 0),
            Reading::Available { value: MemoryBytes { total: 100, available: 0 } }
        );
        assert!(matches!(validate_drive(100, 101), Reading::Unavailable { .. }));
        assert_eq!(
            validate_drive(100, 0),
            Reading::Available { value: DriveBytes { total: 100, available_to_user: 0 } }
        );
    }
    #[test]
    fn snapshot_roundtrip_keeps_unknown_distinct_from_zero() {
        let snap = Snapshot {
            schema_version: 1,
            captured_unix_ms: 123,
            cpu_interval_ms: 1000,
            cpu_percent: Reading::Unavailable { reason: UnavailableReason::InsufficientSamples },
            memory: validate_memory(100, 0),
            windows_drive: validate_drive(100, 20),
            network_connected: Reading::Unavailable { reason: UnavailableReason::Unsupported },
        };
        let data = serde_json::to_string(&snap).unwrap();
        assert_eq!(serde_json::from_str::<Snapshot>(&data).unwrap(), snap);
    }
}

/// Windows-specific collection is kept apart from the host/UI. The host is
/// responsible for calling this on a background worker, not the UI thread.
#[cfg(target_os = "windows")]
#[allow(unsafe_code)]
pub mod windows;
