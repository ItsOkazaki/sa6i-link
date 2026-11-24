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
//! `Avg. Disk sec/Transfer` is on the same query as the two throughput counters
//! because PDH has already opened and sampled the `PhysicalDisk` object; a second
//! query would double the per-sample cost to read a number from a counter that is
//! sitting right there.
//!
//! A zero return is `ERROR_SUCCESS`; PDH also reports "*the call* worked but
//! *the data* is invalid" through the counter's own `CStatus`, so both are
//! checked before a number is believed.

#[cfg(windows)]
mod imp {
    use sa6i_link_intel::{
        Bytes, DiskIoSample, GpuAdapter, GpuSample, MetricState, WhyUnknown,
    };

    use windows::core::{HSTRING, PCWSTR};
    use windows::Win32::System::Performance::{
        PDH_CSTATUS_NO_OBJECT, PDH_FMT_COUNTERVALUE, PDH_FMT_COUNTERVALUE_ITEM_W, PDH_FMT_DOUBLE,
        PDH_HCOUNTER, PDH_HQUERY, PDH_INVALID_PATH, PDH_MORE_DATA, PdhAddEnglishCounterW,
        PdhCloseQuery, PdhCollectQueryData, PdhGetFormattedCounterArrayW,
        PdhGetFormattedCounterValue, PdhOpenQueryW,
    };

    /// Summed over physical disks, which is what Task Manager's Performance tab
    /// shows and what "the disk is busy" means to a person.
    const READ_PATH: &str = "\\PhysicalDisk(_Total)\\Disk Read Bytes/sec";
    const WRITE_PATH: &str = "\\PhysicalDisk(_Total)\\Disk Write Bytes/sec";
    /// Seconds per transfer, not bytes: this is the counter that says whether the
    /// disk is the slow thing or merely the busy one.
    const TRANSFER_PATH: &str = "\\PhysicalDisk(_Total)\\Avg. Disk sec/Transfer";

    /// Hard faults resolved by reading from disk. The `Memory` object, not
    /// `PhysicalDisk`, which is why it needs its own query.
    const PAGES_PATH: &str = "\\Memory\\Pages Input/sec";

    /// GPU counters exist from Windows 10 1709 (Fall Creators Update) and need a
    /// WDDM 2.0 driver; on older systems the counter set is simply absent, which
    /// `reason_of` turns into an honest "not on this version".
    const USED_PATH: &str = "\\GPU Adapter Memory(*)\\Dedicated Usage";
    const LIMIT_PATH: &str = "\\GPU Adapter Memory(*)\\Dedicated Limit";

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
        transfer: PDH_HCOUNTER,
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
            let mut transfer = PDH_HCOUNTER::default();
            let read_path = HSTRING::from(READ_PATH);
            let write_path = HSTRING::from(WRITE_PATH);
            let transfer_path = HSTRING::from(TRANSFER_PATH);
            // SAFETY: the query is open; each counter handle is written into a
            // local that is moved into the struct, and the query closes them.
            unsafe {
                if PdhAddEnglishCounterW(query, &read_path, 0, &mut read) != 0
                    || PdhAddEnglishCounterW(query, &write_path, 0, &mut write) != 0
                    || PdhAddEnglishCounterW(query, &transfer_path, 0, &mut transfer) != 0
                {
                    let _ = PdhCloseQuery(query);
                    return None;
                }
            }
            Some(Self { query, read, write, transfer, collected_once: false })
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
                avg_seconds_per_transfer: number(self.transfer),
            }
        }
    }

    /// `\Memory\Pages Input/sec`: hard faults resolved from disk.
    ///
    /// Its own query rather than a counter added to the disk one. PDH would accept
    /// both objects in a single query, but a machine whose `PhysicalDisk` counters
    /// fail should still be able to report paging, and the reverse: one broken
    /// object should not take the other's number with it. A second
    /// `PdhCollectQueryData` per second costs microseconds.
    #[derive(Debug)]
    pub struct MemoryCounters {
        query: PDH_HQUERY,
        pages: PDH_HCOUNTER,
        collected_once: bool,
    }

    impl MemoryCounters {
        /// Open the query, or `None` if this machine will not give us one.
        #[allow(unsafe_code)]
        pub fn new() -> Option<Self> {
            let mut query = PDH_HQUERY::default();
            // SAFETY: a null data source means "this machine"; the query handle is
            // owned by the returned struct and closed in `Drop`.
            if unsafe { PdhOpenQueryW(PCWSTR::null(), 0, &mut query) } != 0 {
                return None;
            }
            let mut pages = PDH_HCOUNTER::default();
            let pages_path = HSTRING::from(PAGES_PATH);
            // SAFETY: the query is open; the counter handle is written into a local
            // that is moved into the struct, and the query closes it.
            unsafe {
                if PdhAddEnglishCounterW(query, &pages_path, 0, &mut pages) != 0 {
                    let _ = PdhCloseQuery(query);
                    return None;
                }
            }
            Some(Self { query, pages, collected_once: false })
        }

        /// Collect once and read the counter, or say why not.
        #[allow(unsafe_code)]
        pub fn read(&mut self) -> MetricState<f32> {
            // SAFETY: `query` is a live handle owned by `self`.
            if unsafe { PdhCollectQueryData(self.query) } != 0 {
                return MetricState::Unknown(WhyUnknown::CollectorFailed);
            }
            if !self.collected_once {
                // A rate with no interval behind it is a rate PDH reports as 0,
                // and 0 pages per second is what an idle machine looks like.
                self.collected_once = true;
                return MetricState::Unknown(WhyUnknown::NotSampledYet);
            }
            number(self.pages)
        }
    }

    /// Dedicated GPU memory per adapter, for Windows 10 1709 and later.
    ///
    /// This is the machine-wide answer, which `QueryVideoMemoryInfo` is not: that
    /// call reports the calling *process*'s usage on one adapter, and presenting
    /// it as "GPU memory pressure" would be a true number answering the wrong
    /// question. The counters below are what Task Manager reads.
    #[derive(Debug)]
    pub struct GpuCounters {
        query: PDH_HQUERY,
        used: PDH_HCOUNTER,
        limit: PDH_HCOUNTER,
    }

    impl GpuCounters {
        /// Open the query, or say why this machine has no GPU counters.
        ///
        /// A missing counter set (Windows 8.1 or older, a driver without WDDM
        /// 2.0 GPU counters) is not a failure of ours, so it is reported as
        /// `Unsupported(NotOnThisWindowsVersion)`; anything else is a real
        /// failure and says so.
        #[allow(unsafe_code)]
        pub fn new() -> Result<Self, WhyUnknown> {
            let mut query = PDH_HQUERY::default();
            // SAFETY: a null data source means "this machine"; the handle is
            // owned by the returned struct and closed in `Drop`.
            if unsafe { PdhOpenQueryW(PCWSTR::null(), 0, &mut query) } != 0 {
                return Err(WhyUnknown::CollectorFailed);
            }
            let mut used = PDH_HCOUNTER::default();
            let mut limit = PDH_HCOUNTER::default();
            let used_path = HSTRING::from(USED_PATH);
            let limit_path = HSTRING::from(LIMIT_PATH);
            // SAFETY: the query is open and is closed on every failure path.
            unsafe {
                let first = PdhAddEnglishCounterW(query, &used_path, 0, &mut used);
                if first != 0 {
                    let _ = PdhCloseQuery(query);
                    return Err(reason_of(first));
                }
                let second = PdhAddEnglishCounterW(query, &limit_path, 0, &mut limit);
                if second != 0 {
                    let _ = PdhCloseQuery(query);
                    return Err(reason_of(second));
                }
            }
            Ok(Self { query, used, limit })
        }

        /// Collect once and read every adapter.
        #[allow(unsafe_code)]
        pub fn read(&mut self) -> MetricState<GpuSample> {
            // SAFETY: `query` is a live handle owned by `self`.
            if unsafe { PdhCollectQueryData(self.query) } != 0 {
                return MetricState::Unknown(WhyUnknown::CollectorFailed);
            }
            let (Some(used), Some(limits)) = (instances(self.used), instances(self.limit)) else {
                return MetricState::Unknown(WhyUnknown::CollectorFailed);
            };
            let mut adapters: Vec<GpuAdapter> = used
                .into_iter()
                .map(|(instance, bytes)| GpuAdapter {
                    dedicated_used: MetricState::Value(Bytes(bytes)),
                    dedicated_limit: limits
                        .iter()
                        .find(|(name, _)| *name == instance)
                        .map_or(MetricState::Unknown(WhyUnknown::CollectorFailed), |(_, limit)| {
                            MetricState::Value(Bytes(*limit))
                        }),
                    instance,
                })
                .collect();
            // Heaviest first, so a page that shows one shows the discrete GPU.
            adapters.sort_by_key(|a| std::cmp::Reverse(a.dedicated_limit.value().map_or(0, |l| l.0)));
            if adapters.is_empty() {
                // A machine with a display always has one adapter; no items
                // means the counters are there but empty, which is a failure.
                return MetricState::Unknown(WhyUnknown::CollectorFailed);
            }
            MetricState::Value(GpuSample { adapters })
        }
    }

    impl Drop for GpuCounters {
        #[allow(unsafe_code)]
        fn drop(&mut self) {
            // SAFETY: closing the query this struct opened, exactly once.
            let _ = unsafe { PdhCloseQuery(self.query) };
        }
    }

    /// Why `PdhAddEnglishCounterW` refused a path.
    fn reason_of(status: u32) -> WhyUnknown {
        // An absent object or an unreadable path is what an old Windows or a
        // driver without GPU counters looks like; everything else is a fault.
        if status == PDH_CSTATUS_NO_OBJECT || status == PDH_INVALID_PATH {
            WhyUnknown::NotOnThisWindowsVersion
        } else {
            WhyUnknown::CollectorFailed
        }
    }

    /// Every instance of one counter, as `(instance name, value)`.
    ///
    /// PDH answers a wildcard path with an array of items, each carrying the
    /// instance name and a formatted value. The buffer is a `Vec<u64>` so the
    /// items are 8-byte aligned, and the names are copied out before it drops.
    #[allow(unsafe_code)]
    fn instances(counter: PDH_HCOUNTER) -> Option<Vec<(String, u64)>> {
        let mut bytes = 0u32;
        let mut count = 0u32;
        // SAFETY: a null item buffer asks only for the size, which PDH reports
        // with PDH_MORE_DATA.
        let sized = unsafe {
            PdhGetFormattedCounterArrayW(counter, PDH_FMT_DOUBLE, &mut bytes, &mut count, None)
        };
        if sized != PDH_MORE_DATA && sized != 0 {
            return None;
        }
        if count == 0 || bytes == 0 {
            return Some(Vec::new());
        }
        let words = (bytes as usize).div_ceil(8) + 8;
        let mut buffer = vec![0u64; words];
        let mut filled = u32::try_from(buffer.len() * 8).ok()?;
        let mut items = 0u32;
        let items_ptr = buffer.as_mut_ptr().cast::<PDH_FMT_COUNTERVALUE_ITEM_W>();
        // SAFETY: `buffer` is a live allocation of `filled` bytes, aligned for
        // the item struct, and is exactly what the call is told it has.
        let read = unsafe {
            PdhGetFormattedCounterArrayW(
                counter,
                PDH_FMT_DOUBLE,
                &mut filled,
                &mut items,
                Some(items_ptr),
            )
        };
        if read != 0 {
            return None;
        }
        let mut out = Vec::with_capacity(items as usize);
        for index in 0..items as usize {
            // SAFETY: PDH filled `items` entries starting at `items_ptr`.
            let item = unsafe { &*items_ptr.add(index) };
            if item.FmtValue.CStatus != 0 {
                continue;
            }
            // SAFETY: `doubleValue` is the member PDH_FMT_DOUBLE fills.
            let value = unsafe { item.FmtValue.Anonymous.doubleValue };
            if !value.is_finite() || value < 0.0 {
                continue;
            }
            out.push((name_of(item), value as u64));
        }
        Some(out)
    }

    /// The instance name of a counter item, copied out of PDH's buffer.
    #[allow(unsafe_code)]
    fn name_of(item: &PDH_FMT_COUNTERVALUE_ITEM_W) -> String {
        if item.szName.0.is_null() {
            return String::new();
        }
        let mut len = 0usize;
        // SAFETY: PDH promises a null-terminated string for the life of the
        // buffer this item points into.
        while unsafe { *item.szName.0.add(len) } != 0 {
            len += 1;
        }
        // SAFETY: `len` counts the units before that NUL.
        let units = unsafe { std::slice::from_raw_parts(item.szName.0, len) };
        String::from_utf16_lossy(units)
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

    /// A formatted double counter, as `f32`.
    ///
    /// The same two checks as [`formatted`] - the call and the counter's own status -
    /// and one more: a negative or non-finite value is a broken counter. Zero is kept,
    /// because "no transfers happened" and "nothing faulted" are real readings and the
    /// rules know what they mean.
    ///
    /// It carries no unit in its name on purpose: it reads a duration in seconds and a
    /// rate in pages per second, and a function called `seconds` returning a rate is
    /// how a units bug gets written.
    #[allow(unsafe_code)]
    fn number(counter: PDH_HCOUNTER) -> MetricState<f32> {
        let mut value = PDH_FMT_COUNTERVALUE::default();
        // SAFETY: `value` is a valid writable PDH_FMT_COUNTERVALUE, and the union is
        // read as the variant the requested format filled in.
        let status = unsafe { PdhGetFormattedCounterValue(counter, PDH_FMT_DOUBLE, None, &mut value) };
        if status != 0 || value.CStatus != 0 {
            return MetricState::Unknown(WhyUnknown::CollectorFailed);
        }
        // SAFETY: `doubleValue` is the member PDH_FMT_DOUBLE fills.
        let number = unsafe { value.Anonymous.doubleValue };
        if number.is_finite() && number >= 0.0 {
            MetricState::Value(number as f32)
        } else {
            MetricState::Unknown(WhyUnknown::CollectorFailed)
        }
    }
}


#[cfg(not(windows))]
mod imp {
    use sa6i_link_intel::{DiskIoSample, GpuSample, MetricState, WhyUnknown};

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

    /// No performance counters off Windows, and `new` says so.
    #[derive(Debug)]
    pub struct MemoryCounters;

    impl MemoryCounters {
        pub fn new() -> Option<Self> {
            None
        }

        pub fn read(&mut self) -> MetricState<f32> {
            MetricState::Unsupported(WhyUnknown::NotOnThisWindowsVersion)
        }
    }

    /// No performance counters off Windows, and `new` says so.
    #[derive(Debug)]
    pub struct GpuCounters;

    impl GpuCounters {
        pub fn new() -> Result<Self, WhyUnknown> {
            Err(WhyUnknown::NotOnThisWindowsVersion)
        }

        pub fn read(&mut self) -> MetricState<GpuSample> {
            MetricState::Unsupported(WhyUnknown::NotOnThisWindowsVersion)
        }
    }
}

pub use imp::{DiskCounters, GpuCounters, MemoryCounters};
