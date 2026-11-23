// SPDX-License-Identifier: MPL-2.0
//! Windows collectors for the Sa6i intelligence core.
//!
//! Everything here reads what Windows will tell an ordinary user without an
//! administrator prompt. That is a product decision, not an oversight: the
//! Monitor page has to work on a locked-down machine, so anything that needs
//! elevation is reported as [`WhyUnknown::NeedsElevation`] instead of being
//! attempted and failing mysteriously.
//!
//! Slice 1 covers CPU, memory, volumes and uptime. Per-core CPU, disk
//! throughput, GPU memory and per-process detail need APIs that are either
//! heavier (`PdhAddEnglishCounter`) or version-gated (`QueryVideoMemoryInfo`),
//! and land in the next slice with their own fixtures.

use std::time::Instant;

use sa6i_link_intel::{
    Bytes, Collector, CpuSample, MemorySample, MetricState, Snapshot, Timestamp, VolumeSample,
    WhyUnknown,
};

/// A Windows collector. Keeps the previous CPU sample, because a rate needs two.
#[derive(Debug)]
pub struct WindowsCollector {
    started: Instant,
    previous_cpu: Option<CpuTimes>,
    seq: u64,
}

impl Default for WindowsCollector {
    fn default() -> Self {
        Self::new()
    }
}

impl WindowsCollector {
    pub fn new() -> Self {
        Self {
            started: Instant::now(),
            previous_cpu: None,
            seq: 0,
        }
    }

    /// The next snapshot, with the sequence and monotonic clock handled here.
    pub fn next_snapshot(&mut self) -> Snapshot {
        self.seq += 1;
        let monotonic_ms = u64::try_from(self.started.elapsed().as_millis()).unwrap_or(u64::MAX);
        self.sample(self.seq, monotonic_ms)
    }
}

impl Collector for WindowsCollector {
    fn sample(&mut self, seq: u64, monotonic_ms: u64) -> Snapshot {
        let taken_at = Timestamp::now();
        let cpu = self.cpu();
        let memory = read_memory();
        let volumes = read_volumes();
        let uptime = read_uptime();
        Snapshot {
            seq,
            taken_at,
            monotonic_ms,
            cpu,
            memory,
            volumes,
            uptime,
        }
    }
}

impl WindowsCollector {
    fn cpu(&mut self) -> CpuSample {
        let Some(now) = read_cpu_times() else {
            return CpuSample { percent: MetricState::Unknown(WhyUnknown::CollectorFailed) };
        };
        let previous = self.previous_cpu.replace(now);
        let Some(previous) = previous else {
            // The first sample has no interval to divide by.
            return CpuSample { percent: MetricState::Unknown(WhyUnknown::NotSampledYet) };
        };
        match now.percent_busy_since(previous) {
            Some(percent) => CpuSample { percent: MetricState::Value(percent) },
            // A counter that went backwards (a suspend, a firmware quirk) is
            // not a measurement.
            None => CpuSample { percent: MetricState::Unknown(WhyUnknown::CollectorFailed) },
        }
    }
}

/// Cumulative CPU counters, in 100 ns ticks, as `GetSystemTimes` reports them.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CpuTimes {
    pub idle: u64,
    pub kernel: u64,
    pub user: u64,
}

impl CpuTimes {
    /// Percent busy between `self` and `previous`.
    ///
    /// `kernel` already includes idle time, so the total is kernel + user and
    /// the busy part is total − idle. Returns `None` when there is no interval
    /// or a counter went backwards.
    pub fn percent_busy_since(self, previous: Self) -> Option<f32> {
        let idle = self.idle.checked_sub(previous.idle)?;
        let kernel = self.kernel.checked_sub(previous.kernel)?;
        let user = self.user.checked_sub(previous.user)?;
        let total = kernel.checked_add(user)?;
        if total == 0 {
            return None;
        }
        let busy = total.saturating_sub(idle);
        let percent = busy as f64 / total as f64 * 100.0;
        Some(percent.clamp(0.0, 100.0) as f32)
    }
}

#[cfg(windows)]
mod platform {
    use super::*;
    use sa6i_link_intel::VolumeKind;

    use windows::Win32::Foundation::FILETIME;
    use windows::Win32::Storage::FileSystem::{
        GetDiskFreeSpaceExW, GetDriveTypeW, GetLogicalDriveStringsW,
    };
    use windows::Win32::System::SystemInformation::{
        GetSystemTimes, GetTickCount64, GlobalMemoryStatusEx, MEMORYSTATUSEX,
    };
    use windows::core::HSTRING;

    fn ticks(time: FILETIME) -> u64 {
        (u64::from(time.dwHighDateTime) << 32) | u64::from(time.dwLowDateTime)
    }

    pub(super) fn read_cpu_times() -> Option<CpuTimes> {
        let mut idle = FILETIME::default();
        let mut kernel = FILETIME::default();
        let mut user = FILETIME::default();
        // SAFETY: three valid writable stack locals; the call only writes them.
        unsafe { GetSystemTimes(Some(&mut idle), Some(&mut kernel), Some(&mut user)) }.ok()?;
        Some(CpuTimes {
            idle: ticks(idle),
            kernel: ticks(kernel),
            user: ticks(user),
        })
    }

    pub(super) fn read_memory() -> MemorySample {
        let mut status = MEMORYSTATUSEX {
            dwLength: std::mem::size_of::<MEMORYSTATUSEX>() as u32,
            ..Default::default()
        };
        // SAFETY: `status` is a valid, correctly-sized MEMORYSTATUSEX.
        if unsafe { GlobalMemoryStatusEx(&mut status) }.is_err() {
            let failed = MetricState::Unknown(WhyUnknown::CollectorFailed);
            return MemorySample {
                total: failed,
                available: failed,
                commit_limit: failed,
                commit_used: failed,
            };
        }
        // `ullTotalPageFile` is the commit limit, `ullAvailPageFile` what is
        // left of it, so their difference is the commit charge.
        let commit_limit = status.ullTotalPageFile;
        let commit_available = status.ullAvailPageFile.min(commit_limit);
        MemorySample {
            total: MetricState::Value(Bytes(status.ullTotalPhys)),
            available: MetricState::Value(Bytes(status.ullAvailPhys)),
            commit_limit: MetricState::Value(Bytes(commit_limit)),
            commit_used: MetricState::Value(Bytes(commit_limit - commit_available)),
        }
    }

    /// `GetDriveTypeW` result, as documented, without depending on the constant
    /// names matching across `windows` versions.
    fn kind_of(drive_type: u32) -> VolumeKind {
        match drive_type {
            2 => VolumeKind::Removable,
            3 => VolumeKind::Fixed,
            4 => VolumeKind::Network,
            5 => VolumeKind::Optical,
            6 => VolumeKind::Ram,
            _ => VolumeKind::Unknown,
        }
    }

    pub(super) fn read_volumes() -> Vec<VolumeSample> {
        // Length in UTF-16 units, including the final double NUL.
        // SAFETY: a size query with a null buffer writes nothing.
        let required = unsafe { GetLogicalDriveStringsW(0, None) };
        if required == 0 {
            return Vec::new();
        }
        let mut buffer = vec![0u16; required as usize + 1];
        // SAFETY: the buffer is at least `required` units, which is what the
        // call was told it has.
        let written = unsafe {
            GetLogicalDriveStringsW(buffer.len() as u32, Some(buffer.as_mut_ptr()))
        };
        if written == 0 {
            return Vec::new();
        }

        let mut volumes = Vec::new();
        let mut start = 0usize;
        for (end, unit) in buffer[..written as usize].iter().enumerate() {
            if *unit != 0 {
                continue;
            }
            if end == start {
                break; // the double NUL that ends the list
            }
            let mount = String::from_utf16_lossy(&buffer[start..end]);
            start = end + 1;

            let drive_type = {
                let wide = HSTRING::from(mount.as_str());
                // SAFETY: a NUL-terminated path string that lives for the call.
                unsafe { GetDriveTypeW(&wide) }
            };
            let kind = kind_of(drive_type);
            let (total, free) = free_space(&mount);
            // Unreadable network and optical drives are not the user's problem
            // and would only add noise to the list.
            if !kind.is_local_storage() && !total.is_known() {
                continue;
            }
            volumes.push(VolumeSample { mount, kind, total, free });
        }
        volumes.sort_by(|a, b| a.mount.cmp(&b.mount));
        volumes
    }

    fn free_space(mount: &str) -> (MetricState<Bytes>, MetricState<Bytes>) {
        let wide = HSTRING::from(mount);
        let mut free = 0u64;
        let mut total = 0u64;
        // SAFETY: two valid writable u64 locals; the path lives for the call.
        let ok = unsafe { GetDiskFreeSpaceExW(&wide, Some(&mut free), Some(&mut total), None) };
        match ok {
            Ok(()) => (MetricState::Value(Bytes(total)), MetricState::Value(Bytes(free))),
            Err(_) => (
                MetricState::Unknown(WhyUnknown::CollectorFailed),
                MetricState::Unknown(WhyUnknown::CollectorFailed),
            ),
        }
    }

    pub(super) fn read_uptime() -> MetricState<u64> {
        // SAFETY: no arguments, no state.
        let ms = unsafe { GetTickCount64() };
        MetricState::Value(ms / 1000)
    }
}

#[cfg(not(windows))]
mod platform {
    use super::*;

    const REASON: WhyUnknown = WhyUnknown::NotOnThisWindowsVersion;

    pub(super) fn read_cpu_times() -> Option<CpuTimes> {
        None
    }
    pub(super) fn read_memory() -> MemorySample {
        MemorySample {
            total: MetricState::Unsupported(REASON),
            available: MetricState::Unsupported(REASON),
            commit_limit: MetricState::Unsupported(REASON),
            commit_used: MetricState::Unsupported(REASON),
        }
    }
    pub(super) fn read_volumes() -> Vec<VolumeSample> {
        Vec::new()
    }
    pub(super) fn read_uptime() -> MetricState<u64> {
        MetricState::Unsupported(REASON)
    }
}

use platform::{read_cpu_times, read_memory, read_uptime, read_volumes};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cpu_percent_is_a_ratio_of_the_interval() {
        let previous = CpuTimes { idle: 1_000, kernel: 2_000, user: 1_000 };
        // 100 more ticks of kernel (of which 50 idle) and 100 of user:
        // total 200, busy 150, so 75 %.
        let now = CpuTimes { idle: 1_050, kernel: 2_100, user: 1_100 };
        assert_eq!(now.percent_busy_since(previous), Some(75.0));
    }

    #[test]
    fn an_idle_machine_is_zero_not_unknown() {
        let previous = CpuTimes { idle: 0, kernel: 100, user: 100 };
        let now = CpuTimes { idle: 100, kernel: 200, user: 100 };
        assert_eq!(now.percent_busy_since(previous), Some(0.0));
    }

    #[test]
    fn no_interval_or_a_backwards_counter_is_unknown() {
        let same = CpuTimes { idle: 10, kernel: 20, user: 30 };
        assert_eq!(same.percent_busy_since(same), None);
        let later = CpuTimes { idle: 20, kernel: 30, user: 40 };
        let earlier = CpuTimes { idle: 10, kernel: 20, user: 30 };
        assert_eq!(earlier.percent_busy_since(later), None);
    }

    #[test]
    fn percent_is_clamped_when_the_kernel_counter_disagrees() {
        // kernel can lag idle by a tick on some firmware; the result must stay
        // a percentage rather than going negative.
        let previous = CpuTimes { idle: 100, kernel: 100, user: 100 };
        let now = CpuTimes { idle: 150, kernel: 120, user: 150 };
        let percent = now.percent_busy_since(previous).unwrap();
        assert!((0.0..=100.0).contains(&percent), "{percent}");
    }

    #[test]
    fn a_collector_that_runs_reports_its_own_sequence() {
        let mut collector = WindowsCollector::new();
        let first = collector.next_snapshot();
        let second = collector.next_snapshot();
        assert_eq!(first.seq, 1);
        assert_eq!(second.seq, 2);
        assert!(second.monotonic_ms >= first.monotonic_ms);
        // The first sample can never know a rate. On a machine without these
        // collectors the reason is different, but it is never a number.
        assert!(!first.cpu.percent.is_known());
    }
}
