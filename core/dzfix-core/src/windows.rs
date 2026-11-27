// SPDX-License-Identifier: GPL-3.0-or-later
//! Read-only Windows APIs. No WMI, driver, shell, elevation, file traversal,
//! process manipulation or network request. Caller supplies network status
//! from an independently checked collector; absence is always explicit.
use crate::{CpuTimes, Reading, Snapshot, UnavailableReason, cpu_percent, validate_drive, validate_memory};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

#[repr(C)]
#[derive(Default)]
struct FileTime {
    low: u32,
    high: u32,
}
impl FileTime {
    fn ticks(&self) -> u64 {
        (u64::from(self.high) << 32) | u64::from(self.low)
    }
}
#[repr(C)]
struct MemoryStatusEx {
    length: u32,
    memory_load: u32,
    total_phys: u64,
    avail_phys: u64,
    total_page_file: u64,
    avail_page_file: u64,
    total_virtual: u64,
    avail_virtual: u64,
    avail_extended_virtual: u64,
}
#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetSystemTimes(idle: *mut FileTime, kernel: *mut FileTime, user: *mut FileTime) -> i32;
    fn GlobalMemoryStatusEx(status: *mut MemoryStatusEx) -> i32;
    fn GetWindowsDirectoryW(buffer: *mut u16, size: u32) -> u32;
    fn GetDiskFreeSpaceExW(path: *const u16, available: *mut u64, total: *mut u64, free: *mut u64) -> i32;
}

fn system_times() -> Option<CpuTimes> {
    let (mut idle, mut kernel, mut user) = (FileTime::default(), FileTime::default(), FileTime::default());
    // SAFETY: pointers refer to writable, correctly laid out FILETIME structs.
    let ok = unsafe { GetSystemTimes(&mut idle, &mut kernel, &mut user) };
    (ok != 0).then(|| CpuTimes { idle: idle.ticks(), kernel: kernel.ticks(), user: user.ticks() })
}
fn memory() -> Reading<crate::MemoryBytes> {
    let mut status = MemoryStatusEx {
        length: std::mem::size_of::<MemoryStatusEx>() as u32,
        memory_load: 0,
        total_phys: 0,
        avail_phys: 0,
        total_page_file: 0,
        avail_page_file: 0,
        total_virtual: 0,
        avail_virtual: 0,
        avail_extended_virtual: 0,
    };
    // SAFETY: initialized MEMORYSTATUSEX with correct size and valid pointer.
    if unsafe { GlobalMemoryStatusEx(&mut status) } == 0 {
        Reading::Unavailable { reason: UnavailableReason::Error }
    } else {
        validate_memory(status.total_phys, status.avail_phys)
    }
}
fn drive() -> Reading<crate::DriveBytes> {
    let mut path = [0u16; 32768];
    // SAFETY: buffer holds the stated number of writable UTF-16 code units.
    let n = unsafe { GetWindowsDirectoryW(path.as_mut_ptr(), path.len() as u32) } as usize;
    if n == 0 || n >= path.len() {
        return Reading::Unavailable { reason: UnavailableReason::Error };
    }
    path[n] = 0;
    let (mut available, mut total) = (0u64, 0u64);
    // SAFETY: path is NUL-terminated and outputs point to initialized u64s.
    let ok = unsafe { GetDiskFreeSpaceExW(path.as_ptr(), &mut available, &mut total, std::ptr::null_mut()) };
    if ok == 0 {
        Reading::Unavailable { reason: UnavailableReason::Error }
    } else {
        validate_drive(total, available)
    }
}

/// A bounded 1–10 second CPU average plus point-in-time memory and drive
/// readings. Values cover only the processor group represented by Windows'
/// GetSystemTimes on systems with more than one processor group. Caller must
/// expose this limitation and label the duration, not claim a load diagnosis.
/// Sleep is intentional and this function must only run on a worker thread.
pub fn collect(interval: Duration, network_connected: Reading<bool>) -> Result<Snapshot, &'static str> {
    if !(Duration::from_secs(1)..=Duration::from_secs(10)).contains(&interval) {
        return Err("interval outside 1–10 seconds");
    }
    let start = Instant::now();
    let first = system_times();
    std::thread::sleep(interval);
    let last = system_times();
    let elapsed_ms = start.elapsed().as_millis().min(u128::from(u64::MAX)) as u64;
    let cpu_percent = match (first, last) {
        (Some(a), Some(b)) => cpu_percent(a, b),
        _ => Reading::Unavailable { reason: UnavailableReason::Error },
    };
    let captured_unix_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis().min(u128::from(u64::MAX)) as u64)
        .unwrap_or(0);
    Ok(Snapshot {
        schema_version: Snapshot::SCHEMA_VERSION,
        captured_unix_ms,
        cpu_interval_ms: elapsed_ms,
        cpu_percent,
        memory: memory(),
        windows_drive: drive(),
        network_connected,
    })
}
