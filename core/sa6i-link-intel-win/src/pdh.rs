// SPDX-License-Identifier: MPL-2.0
//! Disk throughput, from the performance counters Windows already keeps.
//!
//! `PhysicalDisk` counters are read in **English** (`PdhAddEnglishCounterW`),
//! so a French or Arabic Windows reports the same counter as an English one.
//! That is not a detail: counter display names are localised, and a collector
//! that asked for `\PhysicalDisk(_Total)\Disk Read Bytes/sec` on a localised
//! machine would find nothing and quietly report 0 B/s forever.
//!
//! Everything here is optional. A machine where performance counters are
//! disabled, an account without access, or a PDH that refuses the query yields
//! `Unknown` with a reason — never 0 bytes per second, which is what an idle
//! disk and a broken collector both look like on a graph.
//!
//! Every signature used below was read from the generated documentation for
//! `windows` 0.62.2 rather than recalled:
//!
//! - `PdhOpenQueryW(PCWSTR, usize, *mut PDH_HQUERY) -> u32`
//! - `PdhAddEnglishCounterW(PDH_HQUERY, PCWSTR, usize, *mut PDH_HCOUNTER) -> u32`
//! - `PdhCollectQueryData(PDH_HQUERY) -> u32`
//! - `PdhGetFormattedCounterValue(PDH_HCOUNTER, PDH_FMT, Option<*mut u32>,
//!   *mut PDH_FMT_COUNTERVALUE) -> u32`
//! - `PDH_FMT_COUNTERVALUE { CStatus: u32, Anonymous: PDH_FMT_COUNTERVALUE_0 }`
//!   with the union member `doubleValue: f64`
//!
//! A zero return is `ERROR_SUCCESS`; PDH also reports "*the call* worked but
//! *the data* is invalid" through the counter's own `CStatus`, so both are
//! checked before a number is believed.

#[cfg(windows)]
mod imp {
    use sa6i_link_intel::{Bytes, DiskIoSample, MetricState, WhyUnknown};

    use windows::core::{HSTRING, PCWSTR};
    use windows::Win32::System::Performance::{
        PDH_FMT_COUNTERVALUE, PDH_FMT_DOUBLE, PDH_HCOUNTER, PDH_HQUERY, PdhAddEnglishCounterW,
        PdhCloseQuery, PdhCollectQueryData, PdhGetFormattedCounterValue, PdhOpenQueryW,
    };

    /// Summed over physical disks, which is what Task Manager's Performance tab
    /// shows and what "the disk is busy" means to a person.
    const READ_PATH: &str = "\\PhysicalDisk(_Total)\\Disk Read Bytes/sec";
    const WRITE_PATH: &str = "\\PhysicalDisk(_Total)\\Disk Write Bytes/sec";

    /// An open PDH query with the two throughput counters attached.
    ///
    /// Owning the query means the handle is closed in `Drop`: PDH queries are
    /// not reference counted, so leaking one leaks a kernel object per sample.
    ///
    /// The handles are raw pointers, so this type is `!Send`. The collector is
    /// used from the thread that created it, and this code does not pretend to
    /// allow moving the query to another thread.
    #[derive(Debug)]
    pub struct DiskCounters {
        query: PDH_HQUERY,
        read: PDH_HCOUNTER,
        write: PDH_HCOUNTER,
        /// Whether a first collection has happened: a rate needs two points.
        collected_once: bool,
    }

    impl DiskCounters {
        /// Open the query, or `None` if this machine will not give us one.
        #[allow(unsafe_code)]
        pub fn new() -> Option<Self> {
            let mut query = PDH_HQUERY::default();
            // SAFETY: a null data source means "this machine"; the query handle
            // is owned by the returned struct and closed in `Drop`.
            if unsafe { PdhOpenQueryW(PCWSTR::null(), 0, &mut query) } != 0 {
                return None;
            }
            let mut read = PDH_HCOUNTER::default();
            let mut write = PDH_HCOUNTER::default();
            let read_path = HSTRING::from(READ_PATH);
            let write_path = HSTRING::from(WRITE_PATH);
            // SAFETY: the query is open; each counter handle is written into a
            // local that is moved into the struct, and the query closes them.
            unsafe {
                if PdhAddEnglishCounterW(query, &read_path, 0, &mut read) != 0
                    || PdhAddEnglishCounterW(query, &write_path, 0, &mut write) != 0
                {
                    let _ = PdhCloseQuery(query);
                    return None;
                }
            }
            Some(Self { query, read, write, collected_once: false })
        }

        /// Collect once and read both counters.
        #[allow(unsafe_code)]
        pub fn read(&mut self) -> DiskIoSample {
            // SAFETY: `query` is a live handle owned by `self`.
            let collected = unsafe { PdhCollectQueryData(self.query) };
            if collected != 0 {
                return DiskIoSample::unavailable(WhyUnknown::CollectorFailed);
            }
            if !self.collected_once {
                // The first collection has no interval behind it. PDH would
                // report 0, and on a busy disk that 0 is a lie.
                self.collected_once = true;
                return DiskIoSample::unavailable(WhyUnknown::NotSampledYet);
            }
            DiskIoSample {
                read_bytes_per_second: formatted(self.read),
                write_bytes_per_second: formatted(self.write),
            }
        }
    }

    impl Drop for DiskCounters {
        #[allow(unsafe_code)]
        fn drop(&mut self) {
            // SAFETY: closing the query this struct opened, exactly once.
            let _ = unsafe { PdhCloseQuery(self.query) };
        }
    }

    /// One counter's formatted value, as bytes per second.
    #[allow(unsafe_code)]
    fn formatted(counter: PDH_HCOUNTER) -> MetricState<Bytes> {
        let mut value = PDH_FMT_COUNTERVALUE::default();
        // SAFETY: `value` is a valid writable PDH_FMT_COUNTERVALUE, and the
        // union is read as the variant the requested format filled in.
        let status =
            unsafe { PdhGetFormattedCounterValue(counter, PDH_FMT_DOUBLE, None, &mut value) };
        if status != 0 || value.CStatus != 0 {
            return MetricState::Unknown(WhyUnknown::CollectorFailed);
        }
        // SAFETY: `doubleValue` is the member PDH_FMT_DOUBLE fills.
        let bytes = unsafe { value.Anonymous.doubleValue };
        if bytes.is_finite() && bytes >= 0.0 {
            MetricState::Value(Bytes(bytes as u64))
        } else {
            MetricState::Unknown(WhyUnknown::CollectorFailed)
        }
    }
}

#[cfg(not(windows))]
mod imp {
    use sa6i_link_intel::{DiskIoSample, WhyUnknown};

    /// Nothing to query off Windows; `new` says so by returning `None`.
    #[derive(Debug)]
    pub struct DiskCounters;

    impl DiskCounters {
        pub fn new() -> Option<Self> {
            None
        }

        pub fn read(&mut self) -> DiskIoSample {
            DiskIoSample::unavailable(WhyUnknown::NotOnThisWindowsVersion)
        }
    }
}

pub use imp::DiskCounters;
