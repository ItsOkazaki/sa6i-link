// SPDX-License-Identifier: MPL-2.0
//! Windows collectors for the Sa6i intelligence core.
//!
//! Everything here reads what Windows will tell an ordinary user without an
//! administrator prompt. That is a product decision, not an oversight: the
//! Monitor page has to work on a locked-down machine, so anything that needs
//! elevation is reported as [`WhyUnknown::NeedsElevation`] instead of being
//! attempted and failing mysteriously.
//!
//! Slice 1 covers CPU, memory, volumes and uptime; slice 4 adds per-core CPU,
//! slice 6 the heaviest processes, slice 7 disk throughput (see the `pdh` module).
//!
//! GPU memory is still missing on purpose: `QueryVideoMemoryInfo` answers for
//! the calling process on an adapter, not for the machine, so it needs the PDH
//! counter set `\GPU Adapter Memory(*)` instead — the same module `pdh` now
//! uses, which is why that collector comes next rather than first.
//!
//! # `unsafe`
//!
//! The workspace denies `unsafe_code`; this crate is where the C API lives, so
//! each function that calls one carries its own `#[allow(unsafe_code)]` with a
//! `SAFETY:` note on every block. Nothing else in the crate is allowed to be
//! unsafe, which is the point of doing it per function rather than per crate.

use std::time::Instant;

use sa6i_link_intel::{
    Bytes, Collector, CpuSample, DiskIoSample, MemorySample, MetricState, ProcessSample, Snapshot,
    TOP_PROCESSES, Timestamp, VolumeSample, WhyUnknown, top_processes,
};

mod pdh;

/// A Windows collector. Keeps the previous CPU sample, because a rate needs two.
#[derive(Debug)]
pub struct WindowsCollector {
    started: Instant,
    previous_cpu: Option<CpuTimes>,
    /// The previous per-core counters, so a rate can be computed per core.
    previous_cores: Option<Vec<CpuTimes>>,
    /// The disk throughput query, opened once. `None` when this machine will
    /// not give us one, which is reported per sample rather than retried every
    /// second: a disabled counter set does not come back on its own.
    disk: Option<pdh::DiskCounters>,
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
            previous_cores: None,
            disk: pdh::DiskCounters::new(),
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
        let disk_io = match self.disk.as_mut() {
            Some(disk) => disk.read(),
            None => DiskIoSample::unavailable(WhyUnknown::CollectorFailed),
        };
        let processes = platform::read_processes();
        let uptime = read_uptime();
        Snapshot {
            seq,
            taken_at,
            monotonic_ms,
            cpu,
            memory,
            volumes,
            disk_io,
            processes,
            uptime,
        }
    }
}

impl WindowsCollector {
    fn cpu(&mut self) -> CpuSample {
        let per_core = self.cores();
        let Some(now) = read_cpu_times() else {
            let percent = MetricState::Unknown(WhyUnknown::CollectorFailed);
            return CpuSample { percent, per_core };
        };
        let previous = self.previous_cpu.replace(now);
        let Some(previous) = previous else {
            // The first sample has no interval to divide by.
            let percent = MetricState::Unknown(WhyUnknown::NotSampledYet);
            return CpuSample { percent, per_core };
        };
        // A counter that went backwards (a suspend, a firmware quirk) is not a
        // measurement.
        let percent = match now.percent_busy_since(previous) {
            Some(percent) => MetricState::Value(percent),
            None => MetricState::Unknown(WhyUnknown::CollectorFailed),
        };
        CpuSample { percent, per_core }
    }

    /// Per-core percentages, keeping the counters for the next interval.
    ///
    /// `read_core_times` answering `None` empties the list rather than filling
    /// it with zeros: the page draws nothing, which is the truth, instead of
    /// drawing an idle machine, which is a lie with a shape.
    fn cores(&mut self) -> Vec<MetricState<f32>> {
        let Some(now) = read_core_times() else {
            self.previous_cores = None;
            return Vec::new();
        };
        let previous = self.previous_cores.replace(now);
        let current = self.previous_cores.as_deref().unwrap_or(&[]);
        core_states(previous.as_deref(), current)
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

/// Per-core busy percentages from two sets of counters.
///
/// Pure on purpose: the arithmetic is tested on every platform, while the call
/// that produces the counters can only be tested on Windows.
///
/// A core with no previous reading has no interval to divide by, and a counter
/// that went backwards is not a measurement — both are `Unknown` with a reason,
/// and neither is 0.
fn core_states(previous: Option<&[CpuTimes]>, current: &[CpuTimes]) -> Vec<MetricState<f32>> {
    let previous = previous.unwrap_or(&[]);
    current
        .iter()
        .enumerate()
        .map(|(index, now)| match previous.get(index) {
            None => MetricState::Unknown(WhyUnknown::NotSampledYet),
            Some(before) => match now.percent_busy_since(*before) {
                Some(percent) => MetricState::Value(percent),
                None => MetricState::Unknown(WhyUnknown::CollectorFailed),
            },
        })
        .collect()
}

#[cfg(windows)]
mod platform {
    use super::*;
    use sa6i_link_intel::VolumeKind;

    use windows::Win32::Foundation::{CloseHandle, FILETIME};
    use windows::Win32::Storage::FileSystem::{
        GetDiskFreeSpaceExW, GetDriveTypeW, GetLogicalDriveStringsW,
    };
    use windows::Win32::System::ProcessStatus::{
        EnumProcesses, GetProcessMemoryInfo, PROCESS_MEMORY_COUNTERS, PROCESS_MEMORY_COUNTERS_EX,
    };
    use windows::Win32::System::SystemInformation::{
        GetSystemTimes, GetTickCount64, GlobalMemoryStatusEx, MEMORYSTATUSEX,
    };
    use windows::Win32::System::Threading::{
        OpenProcess, PROCESS_NAME_WIN32, PROCESS_QUERY_LIMITED_INFORMATION,
        QueryFullProcessImageNameW,
    };
    use windows::Wdk::System::SystemInformation::{
        NtQuerySystemInformation, SystemProcessorPerformanceInformation,
    };
    use windows::core::HSTRING;

    fn ticks(time: FILETIME) -> u64 {
        (u64::from(time.dwHighDateTime) << 32) | u64::from(time.dwLowDateTime)
    }

    #[allow(unsafe_code)]
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

    /// Per-processor counters, in the calling thread's processor group.
    ///
    /// `NtQuerySystemInformation(SystemProcessorPerformanceInformation)` fills an
    /// array of `SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION`, six 64-bit words per
    /// processor: idle, kernel, user, deferred-procedure, interrupt, then the
    /// interrupt count packed with its padding. That struct is not in the
    /// `windows` crate, so the buffer is read as words instead of declaring a
    /// layout I would be trusting from memory — 48 bytes is exactly six of them.
    #[allow(unsafe_code)]
    pub(super) fn read_core_times() -> Option<Vec<CpuTimes>> {
        const WORD: usize = std::mem::size_of::<u64>();
        const PER_PROCESSOR: usize = 6 * WORD;
        // A null buffer with length 0 is how the required size is asked for.
        let mut needed = 0u32;
        // SAFETY: with a null pointer and a zero length the call writes nothing;
        // it only reports the size it would need.
        unsafe {
            NtQuerySystemInformation(
                SystemProcessorPerformanceInformation,
                std::ptr::null_mut(),
                0,
                &mut needed,
            )
        };
        if needed == 0 {
            return None;
        }
        // Some slack: the call rounds the size up when the buffer is not an
        // exact fit, and an exact-fit buffer makes it fail on some builds.
        let words = (needed as usize).div_ceil(WORD) + 8;
        // `Vec<u64>`, so the allocation is 8-byte aligned as the call assumes;
        // a `Vec<u8>` only guarantees 1.
        let mut buffer = vec![0u64; words];
        let Ok(length) = u32::try_from(buffer.len() * WORD) else {
            return None;
        };
        let mut written = 0u32;
        // SAFETY: `buffer` is a live allocation of `length` bytes and is told so,
        // and it is aligned for the 64-bit stores the kernel performs.
        let status = unsafe {
            NtQuerySystemInformation(
                SystemProcessorPerformanceInformation,
                buffer.as_mut_ptr().cast(),
                length,
                &mut written,
            )
        };
        if status.is_err() {
            return None;
        }
        let bytes = (written as usize).min(buffer.len() * WORD);
        let count = bytes / PER_PROCESSOR;
        let mut cores = Vec::with_capacity(count);
        for processor in buffer[..count * 6].chunks_exact(6) {
            cores.push(CpuTimes {
                idle: processor[0],
                kernel: processor[1],
                user: processor[2],
            });
        }
        Some(cores)
    }

    #[allow(unsafe_code)]
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

    #[allow(unsafe_code)]
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

    #[allow(unsafe_code)]
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

    /// The heaviest processes a standard user can open.
    ///
    /// Each process is opened with `PROCESS_QUERY_LIMITED_INFORMATION` only —
    /// that is what makes this run without an administrator. A process that
    /// cannot be opened is left out of the list rather than listed with zeros:
    /// `System` and other users' sessions are simply absent, which is the
    /// honest version of "no admin prompt".
    #[allow(unsafe_code)]
    pub(super) fn read_processes() -> Vec<ProcessSample> {
        const WIDEST: usize = 65_536;
        let mut capacity = 1024usize;
        loop {
            let mut pids = vec![0u32; capacity];
            let mut written = 0u32;
            let bytes = u32::try_from(pids.len() * std::mem::size_of::<u32>()).unwrap_or(u32::MAX);
            // SAFETY: `pids` is a writable buffer of `bytes` and `written`
            // receives how much of it the call filled.
            let listed = unsafe { EnumProcesses(pids.as_mut_ptr(), bytes, &mut written) };
            if listed.is_err() {
                return Vec::new();
            }
            let per_pid = std::mem::size_of::<u32>();
            let count = (written as usize / per_pid).min(pids.len());
            if count == 0 {
                return Vec::new();
            }
            // A full buffer means there may be more processes than we asked for.
            if count == pids.len() && capacity < WIDEST {
                capacity *= 4;
                continue;
            }
            pids.truncate(count);
            let processes: Vec<ProcessSample> = pids.into_iter().filter_map(process_of).collect();
            return top_processes(processes, TOP_PROCESSES);
        }
    }

    #[allow(unsafe_code)]
    fn process_of(pid: u32) -> Option<ProcessSample> {
        if pid == 0 {
            // The idle process: a name and a size that would both be invented.
            return None;
        }
        // SAFETY: the handle is `PROCESS_QUERY_LIMITED_INFORMATION` only and is
        // closed on every path below; a failed open is `None`, not a guess.
        unsafe {
            let handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid).ok()?;
            let mut buffer = [0u16; 260];
            let mut len = buffer.len() as u32;
            let named = QueryFullProcessImageNameW(
                handle,
                PROCESS_NAME_WIN32,
                windows::core::PWSTR(buffer.as_mut_ptr()),
                &mut len,
            );
            let mut counters = PROCESS_MEMORY_COUNTERS_EX {
                cb: std::mem::size_of::<PROCESS_MEMORY_COUNTERS_EX>() as u32,
                ..Default::default()
            };
            let measured = GetProcessMemoryInfo(
                handle,
                std::ptr::from_mut(&mut counters).cast::<PROCESS_MEMORY_COUNTERS>(),
                counters.cb,
            );
            let _ = CloseHandle(handle);
            if named.is_err() && measured.is_err() {
                return None;
            }
            let name = if named.is_ok() && len > 0 {
                let full = String::from_utf16_lossy(&buffer[..len as usize]);
                full.rsplit('\\').next().unwrap_or(&full).to_owned()
            } else {
                format!("pid {pid}")
            };
            let working_set = if measured.is_ok() {
                MetricState::Value(Bytes(counters.WorkingSetSize as u64))
            } else {
                MetricState::Unknown(WhyUnknown::CollectorFailed)
            };
            Some(ProcessSample { pid, name, working_set })
        }
    }

    #[allow(unsafe_code)]
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
    pub(super) fn read_core_times() -> Option<Vec<CpuTimes>> {
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
    pub(super) fn read_processes() -> Vec<ProcessSample> {
        Vec::new()
    }
    pub(super) fn read_uptime() -> MetricState<u64> {
        MetricState::Unsupported(REASON)
    }
}

use platform::{read_core_times, read_cpu_times, read_memory, read_uptime, read_volumes};

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
    fn per_core_starts_unknown_then_reports_each_core() {
        let first = [CpuTimes { idle: 0, kernel: 100, user: 100 }];
        assert_eq!(core_states(None, &first), vec![MetricState::Unknown(WhyUnknown::NotSampledYet)]);
        // 100 ticks of which all 100 idle: the core was idle for the interval.
        let second = [CpuTimes { idle: 100, kernel: 200, user: 100 }];
        assert_eq!(core_states(Some(&first), &second), vec![MetricState::Value(0.0)]);
    }

    #[test]
    fn a_core_with_no_previous_reading_is_unknown_not_zero() {
        let previous = [CpuTimes { idle: 10, kernel: 20, user: 20 }];
        let current = [
            CpuTimes { idle: 20, kernel: 30, user: 30 },
            CpuTimes { idle: 5, kernel: 5, user: 5 },
        ];
        let states = core_states(Some(&previous), &current);
        assert_eq!(states.len(), 2);
        assert!(states[0].is_known());
        assert_eq!(states[1], MetricState::Unknown(WhyUnknown::NotSampledYet));
    }

    #[test]
    fn a_backwards_core_counter_does_not_poison_the_other_cores() {
        let previous = [
            CpuTimes { idle: 10, kernel: 20, user: 20 },
            CpuTimes { idle: 10, kernel: 20, user: 20 },
        ];
        let current = [
            CpuTimes { idle: 20, kernel: 30, user: 30 },
            CpuTimes { idle: 1, kernel: 2, user: 2 },
        ];
        let states = core_states(Some(&previous), &current);
        assert_eq!(states[0], MetricState::Value(50.0));
        assert_eq!(states[1], MetricState::Unknown(WhyUnknown::CollectorFailed));
    }

    #[test]
    fn the_process_list_is_bounded_named_and_heaviest_first() {
        let mut collector = WindowsCollector::new();
        let snapshot = collector.next_snapshot();
        assert!(snapshot.processes.len() <= TOP_PROCESSES);
        for process in &snapshot.processes {
            // The idle process has no real name or size, so it is never listed.
            assert_ne!(process.pid, 0);
            assert!(!process.name.is_empty());
        }
        let sizes: Vec<u64> = snapshot
            .processes
            .iter()
            .map(|process| process.working_set.value().map_or(0, |bytes| bytes.0))
            .collect();
        assert!(sizes.windows(2).all(|pair| pair[0] >= pair[1]), "{sizes:?}");
        // On a machine with a process table this must actually find something;
        // elsewhere the collector is honest and returns nothing.
        #[cfg(windows)]
        assert!(!snapshot.processes.is_empty(), "a Windows machine always has processes");
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
