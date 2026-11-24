// SPDX-License-Identifier: MPL-2.0
//! The machine model: what Sa6i has measured, and what it could not.
//!
//! The rule this module exists to enforce is that **a missing measurement is a
//! value, not a zero**. [`MetricState`] makes "unavailable" impossible to
//! confuse with "0 %", "0 bytes" or "no problem found" — every consumer has to
//! match on it before it can display anything.

use std::{
    cmp::Ordering,
    time::{SystemTime, UNIX_EPOCH},
};

use serde::{Deserialize, Serialize};

/// Milliseconds since the Unix epoch.
///
/// Snapshots also carry [`Snapshot::monotonic_ms`], because a wall clock can
/// jump (NTP, a manual change, a laptop waking in another timezone) and a
/// duration computed from wall-clock stamps would then be wrong.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(transparent)]
pub struct Timestamp(pub i64);

impl Timestamp {
    /// The current wall-clock time, if the clock is after 1970.
    pub fn now() -> Self {
        let ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| i64::try_from(d.as_millis()).unwrap_or(i64::MAX))
            .unwrap_or(0);
        Self(ms)
    }

    /// `self + ms`, saturating.
    pub fn plus(self, ms: i64) -> Self {
        Self(self.0.saturating_add(ms))
    }

    /// Milliseconds from `earlier` to `self`, saturating at 0.
    pub fn since(self, earlier: Self) -> i64 {
        self.0.saturating_sub(earlier.0).max(0)
    }
}

/// Why a measurement is not a number.
///
/// The distinction matters to the user: `NeedsElevation` can be fixed by a
/// decision, `NotOnThisWindowsVersion` cannot, and `NotCollectedYet` fixes
/// itself on the next sample. None of them mean "fine".
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WhyUnknown {
    /// The first sample cannot know a rate; the second one will.
    NotSampledYet,
    /// Reading this needs administrator rights this build does not ask for.
    NeedsElevation,
    /// The API does not exist on this Windows version.
    NotOnThisWindowsVersion,
    /// The collector exists but failed; the reason is in the log.
    CollectorFailed,
    /// No collector for this metric has been written yet.
    NotCollectedYet,
}

impl WhyUnknown {
    /// One sentence a user could read, without jargon or a false reassurance.
    pub fn explain(self) -> &'static str {
        match self {
            Self::NotSampledYet => "waiting for the second sample",
            Self::NeedsElevation => "requires administrator rights",
            Self::NotOnThisWindowsVersion => "not available on this version of Windows",
            Self::CollectorFailed => "the reading failed",
            Self::NotCollectedYet => "not measured yet",
        }
    }
}

/// A measurement, or the reason there isn't one.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "state", content = "value")]
pub enum MetricState<T> {
    /// A real measurement.
    Value(T),
    /// Should be measurable, is not right now.
    Unknown(WhyUnknown),
    /// This machine cannot provide it at all.
    Unsupported(WhyUnknown),
}

impl<T> MetricState<T> {
    /// The value, if there is one.
    pub fn value(&self) -> Option<&T> {
        match self {
            Self::Value(v) => Some(v),
            _ => None,
        }
    }

    /// Whether a number is present. `false` never means "healthy".
    pub fn is_known(&self) -> bool {
        matches!(self, Self::Value(_))
    }

    /// Why there is no value, if there is not one.
    pub fn why(&self) -> Option<WhyUnknown> {
        match self {
            Self::Value(_) => None,
            Self::Unknown(w) | Self::Unsupported(w) => Some(*w),
        }
    }

    /// The value or a fallback, for call sites that have decided a fallback is
    /// honest (never for display).
    pub fn unwrap_or(self, fallback: T) -> T {
        match self {
            Self::Value(v) => v,
            _ => fallback,
        }
    }
}

/// CPU use since the previous snapshot.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CpuSample {
    /// Percent of total capacity, 0 to 100, averaged over the interval between
    /// this sample and the previous one.
    pub percent: MetricState<f32>,
    /// Percent busy per logical processor, in index order, over the same
    /// interval.
    ///
    /// Empty when per-core data was not collected at all (an older build,
    /// another platform, a failed read). A core that was not measured is
    /// [`MetricState::Unknown`] with its reason, never 0: an idle core and an
    /// unmeasured one look identical in a bar chart and mean opposite things.
    ///
    /// Windows answers this per *processor group*, and this is the group the
    /// sampling thread runs in — on a machine with more than 64 logical
    /// processors the list is that group's cores. `per_core.len()` is how many
    /// were actually measured; the UI says so rather than guessing a total.
    pub per_core: Vec<MetricState<f32>>,
}

/// Physical and committed memory, in bytes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct Bytes(pub u64);

impl Bytes {
    /// Percent used, if the total is known and non-zero.
    pub fn percent_used(self, total: Bytes) -> Option<f32> {
        if total.0 == 0 {
            return None;
        }
        let used = total.0.saturating_sub(self.0.min(total.0));
        Some((used as f64 / total.0 as f64 * 100.0) as f32)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct MemorySample {
    /// Installed physical memory.
    pub total: MetricState<Bytes>,
    /// Hard faults per second that had to be resolved by reading from disk, from
    /// `\Memory\Pages Input/sec`.
    ///
    /// This is the counter that says memory is too small for what is running: an
    /// idle machine reads a handful a second, opening a program spikes into the
    /// thousands for a moment, and a machine that stays in the hundreds is one
    /// whose working set no longer fits. Zero is a real reading - nothing
    /// faulted - and a rule that fired on it would fire on every quiet machine.
    pub pages_input_per_second: MetricState<f32>,
    /// Physically available right now.
    pub available: MetricState<Bytes>,
    /// Commit limit (physical plus page file).
    pub commit_limit: MetricState<Bytes>,
    /// Commit charge: what the system has promised, which can exceed physical.
    pub commit_used: MetricState<Bytes>,
}

impl MemorySample {
    /// Physical memory in use, as a percentage.
    pub fn percent_used(&self) -> MetricState<f32> {
        match (&self.total, &self.available) {
            (MetricState::Value(total), MetricState::Value(avail)) => {
                match avail.percent_used(*total) {
                    Some(p) => MetricState::Value(p),
                    None => MetricState::Unknown(WhyUnknown::CollectorFailed),
                }
            }
            (MetricState::Unsupported(w), _) | (_, MetricState::Unsupported(w)) => {
                MetricState::Unsupported(*w)
            }
            (MetricState::Unknown(w), _) => MetricState::Unknown(*w),
            (_, MetricState::Unknown(w)) => MetricState::Unknown(*w),
        }
    }
}

/// What kind of thing a volume is, as Windows reports it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum VolumeKind {
    Fixed,
    Removable,
    Network,
    Optical,
    Ram,
    Unknown,
}

impl VolumeKind {
    /// Whether a full volume of this kind is worth mentioning to the user.
    pub fn is_local_storage(self) -> bool {
        matches!(self, Self::Fixed | Self::Removable)
    }
}

/// One mounted volume.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct VolumeSample {
    /// The mount root Windows gave, e.g. `"C:\\"`.
    pub mount: String,
    pub kind: VolumeKind,
    pub total: MetricState<Bytes>,
    pub free: MetricState<Bytes>,
}

impl VolumeSample {
    /// Percent of the volume in use.
    pub fn percent_used(&self) -> MetricState<f32> {
        match (&self.total, &self.free) {
            (MetricState::Value(total), MetricState::Value(free)) => {
                match free.percent_used(*total) {
                    Some(p) => MetricState::Value(p),
                    None => MetricState::Unknown(WhyUnknown::CollectorFailed),
                }
            }
            (MetricState::Unsupported(w), _) | (_, MetricState::Unsupported(w)) => {
                MetricState::Unsupported(*w)
            }
            (MetricState::Unknown(w), _) => MetricState::Unknown(*w),
            (_, MetricState::Unknown(w)) => MetricState::Unknown(*w),
        }
    }

    /// `"C:"` for `"C:\\"`, for display and for metric paths.
    pub fn letter(&self) -> &str {
        self.mount.trim_end_matches(['\\', '/'])
    }
}

/// One process, as much of it as a standard user can see.
///
/// Processes the user cannot open (the System process, other users' sessions)
/// are absent rather than listed with zeros — the promise is that nothing here
/// needs an administrator, so the list is honestly what that costs.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProcessSample {
    pub pid: u32,
    /// Executable file name, e.g. `"msedge.exe"`. Empty when it could not be read.
    pub name: String,
    /// Resident memory (the working set), which is what "using 1.2 GB" means to
    /// a person looking at Task Manager.
    pub working_set: MetricState<Bytes>,
    /// Percent of one core over the interval since the previous snapshot — the
    /// number Task Manager's Processes tab shows. A process with several busy
    /// threads may read above 100, and a process seen for the first time reads
    /// [`WhyUnknown::NotSampledYet`], because a rate needs two moments.
    pub cpu_percent: MetricState<f32>,
    /// When the process started, in the collector's own ticks (100 ns units on
    /// Windows), or why that could not be read.
    ///
    /// This is identity, not a measurement. Windows hands a pid to a new process
    /// as soon as the old one exits, so `pid` alone cannot say whether two
    /// samples describe the same program — a rule that tracks a process for ten
    /// minutes needs both halves of the key. It is deliberately **not** published
    /// by [`Snapshot::metrics`]: an `f64` cannot carry a FILETIME exactly, and a
    /// path that is nearly right is worse than one that does not exist.
    pub created: MetricState<u64>,
}

/// How many processes a snapshot carries. Enough to see the problem, few enough
/// that a page can show them all.
pub const TOP_PROCESSES: usize = 8;

fn working_set_bytes(process: &ProcessSample) -> u64 {
    process.working_set.value().map_or(0, |bytes| bytes.0)
}

/// The `limit` processes worth showing, busiest first.
///
/// Pure and total, so the order is testable without a machine. The rule is: the
/// busiest by CPU first (a process using a core is the answer to "what is
/// happening"), then the heaviest by memory (the answer to "what is using my
/// RAM"), then by pid, so two runs over the same machine produce the same list
/// and a screenshot can be compared with a log. On an idle machine every rate is
/// about zero and the list is the heaviest by memory, which is what Task Manager
/// defaults to as well.
///
/// A process whose memory could not be read sorts last rather than pretending to
/// be 0 B, and one whose CPU is not known yet — the first sample after it
/// appeared — sorts below processes that were measured: an unmeasured cost is
/// not a cheap one, but it is not a claim either.
pub fn top_processes(mut processes: Vec<ProcessSample>, limit: usize) -> Vec<ProcessSample> {
    let cpu_of = |process: &ProcessSample| process.cpu_percent.value().copied();
    processes.sort_by(|a, b| {
        let busiest = match (cpu_of(a), cpu_of(b)) {
            (Some(one), Some(two)) => two.partial_cmp(&one).unwrap_or(Ordering::Equal),
            (Some(_), None) => Ordering::Less,
            (None, Some(_)) => Ordering::Greater,
            (None, None) => Ordering::Equal,
        };
        busiest
            .then_with(|| working_set_bytes(b).cmp(&working_set_bytes(a)))
            .then_with(|| a.pid.cmp(&b.pid))
    });
    processes.truncate(limit);
    processes
}

/// Disk throughput, from Windows' `PhysicalDisk` counters.
///
/// Bytes per second, summed over physical disks — the number Task Manager's
/// Performance tab shows. Per-volume throughput would be a different
/// measurement (a volume spanning two disks has no single answer), so this is
/// named for what it actually is.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct DiskIoSample {
    pub read_bytes_per_second: MetricState<Bytes>,
    pub write_bytes_per_second: MetricState<Bytes>,
    /// Average seconds per physical disk transfer, from Windows'
    /// `Avg. Disk sec/Transfer`.
    ///
    /// This is the number that says whether the *disk* is the slow part. A solid
    /// state drive answers in well under a tenth of a millisecond, a mechanical
    /// one in a few, and a queue or a failing disk climbs past a tenth of a
    /// second - at which point everything that touches storage waits and the CPU
    /// looks idle while the machine feels broken.
    ///
    /// Zero means no transfers happened, not "instantaneous": a rule that fires on
    /// zero would fire on every idle machine.
    pub avg_seconds_per_transfer: MetricState<f32>,
}

impl DiskIoSample {
    /// Throughput nobody measured, for the reason given.
    pub fn unavailable(reason: WhyUnknown) -> Self {
        Self {
            read_bytes_per_second: MetricState::Unknown(reason),
            write_bytes_per_second: MetricState::Unknown(reason),
            avg_seconds_per_transfer: MetricState::Unknown(reason),
        }
    }

    /// Whether either direction is a real number.
    pub fn is_known(&self) -> bool {
        self.read_bytes_per_second.is_known() || self.write_bytes_per_second.is_known()
    }
}

/// One graphics adapter, as Windows' GPU performance counters describe it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct GpuAdapter {
    /// The counter instance name, e.g. `luid_0x00000000_0x0000FB33_phys_0`.
    /// It is the only stable identity Windows offers: there is no friendly name
    /// in the counter set, and inventing one from the driver would be a guess.
    pub instance: String,
    /// VRAM in use.
    pub dedicated_used: MetricState<Bytes>,
    /// VRAM the adapter owns. **Zero is a fact, not a failure**: an integrated
    /// GPU has no memory of its own and reports 0 here, which is why the
    /// percentage below refuses to divide by it.
    pub dedicated_limit: MetricState<Bytes>,
}

impl GpuAdapter {
    /// Share of dedicated memory in use, when that question has an answer.
    ///
    /// `None` when either number is unknown, and `None` when the limit is 0 —
    /// an integrated GPU would otherwise report "0 % of nothing", or infinity.
    pub fn percent_used(&self) -> Option<f32> {
        let used = self.dedicated_used.value()?.0;
        let limit = self.dedicated_limit.value()?.0;
        if limit == 0 {
            return None;
        }
        Some((used.min(limit) as f32 / limit as f32) * 100.0)
    }
}

/// The machine's graphics adapters.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct GpuSample {
    pub adapters: Vec<GpuAdapter>,
}

impl GpuSample {
    /// The adapter with the most dedicated memory — the one a game would pick,
    /// and the one worth showing when there are two.
    pub fn heaviest(&self) -> Option<&GpuAdapter> {
        self.adapters.iter().max_by_key(|adapter| {
            adapter.dedicated_limit.value().map_or(0, |limit| limit.0)
        })
    }
}

/// Everything measured at one moment.
///
/// `PartialEq` is derived so tests can assert on whole snapshots, and `seq`
/// makes a snapshot unambiguous even if the wall clock repeats a millisecond.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Snapshot {
    /// Monotonic sample counter, starting at 1.
    pub seq: u64,
    /// Wall-clock time the sample was taken.
    pub taken_at: Timestamp,
    /// Milliseconds since the collector started, for interval maths that must
    /// survive a clock change.
    pub monotonic_ms: u64,
    pub cpu: CpuSample,
    pub memory: MemorySample,
    pub volumes: Vec<VolumeSample>,
    /// Read and write throughput, over physical disks.
    pub disk_io: DiskIoSample,
    /// The graphics adapters, or the reason there are none to report. Absent
    /// rather than empty on a machine whose counters do not exist (Windows 8.1
    /// and older, or a driver with no WDDM 2.0 GPU counters).
    pub gpu: MetricState<GpuSample>,
    /// The busiest (then heaviest) processes, see [`TOP_PROCESSES`]. Empty when processes were
    /// not collected at all.
    pub processes: Vec<ProcessSample>,
    /// Seconds since the machine booted.
    pub uptime: MetricState<u64>,
}

impl Snapshot {
    /// Everything measurable in this snapshot, as `(path, value)` pairs.
    ///
    /// Paths are the contract between rules, evidence and the UI — this is what
    /// "why?" shows the user. A metric that is not a value is simply absent,
    /// because there is nothing to plot.
    pub fn metrics(&self) -> Vec<(String, f64)> {
        let mut out = Vec::new();
        if let MetricState::Value(p) = self.cpu.percent {
            out.push(("cpu.percent".to_owned(), f64::from(p)));
        }
        for (index, core) in self.cpu.per_core.iter().enumerate() {
            if let MetricState::Value(p) = core {
                out.push((format!("cpu.core.{index}.percent"), f64::from(*p)));
            }
        }
        if let MetricState::Value(p) = self.memory.percent_used() {
            out.push(("memory.percent_used".to_owned(), f64::from(p)));
        }
        if let MetricState::Value(total) = self.memory.total {
            out.push(("memory.total_bytes".to_owned(), total.0 as f64));
        }
        if let MetricState::Value(available) = self.memory.available {
            out.push(("memory.available_bytes".to_owned(), available.0 as f64));
        }
        // Commit charge is collected with the rest of the memory sample. It is
        // published here because a rule may not cite a path `metrics()` does not
        // emit — evidence is checked against this list, not against the struct.
        if let MetricState::Value(used) = self.memory.commit_used {
            out.push(("memory.commit_used_bytes".to_owned(), used.0 as f64));
        }
        if let MetricState::Value(limit) = self.memory.commit_limit {
            out.push(("memory.commit_limit_bytes".to_owned(), limit.0 as f64));
        }
        if let MetricState::Value(pages) = self.memory.pages_input_per_second {
            out.push(("memory.pages_input_per_second".to_owned(), f64::from(pages)));
        }
        for volume in &self.volumes {
            if let MetricState::Value(p) = volume.percent_used() {
                out.push((format!("volume.{}.percent_used", volume.letter()), f64::from(p)));
            }
            if let MetricState::Value(free) = volume.free {
                out.push((format!("volume.{}.free_bytes", volume.letter()), free.0 as f64));
            }
            if let MetricState::Value(total) = volume.total {
                out.push((format!("volume.{}.total_bytes", volume.letter()), total.0 as f64));
            }
        }
        if let MetricState::Value(read) = self.disk_io.read_bytes_per_second {
            out.push(("disk.read_bytes_per_second".to_owned(), read.0 as f64));
        }
        if let MetricState::Value(write) = self.disk_io.write_bytes_per_second {
            out.push(("disk.write_bytes_per_second".to_owned(), write.0 as f64));
        }
        if let MetricState::Value(seconds) = self.disk_io.avg_seconds_per_transfer {
            out.push(("disk.seconds_per_transfer".to_owned(), f64::from(seconds)));
        }
        if let MetricState::Value(gpu) = &self.gpu {
            for (index, adapter) in gpu.adapters.iter().enumerate() {
                if let MetricState::Value(used) = adapter.dedicated_used {
                    let path = format!("gpu.adapter.{index}.dedicated_used_bytes");
                    out.push((path, used.0 as f64));
                }
                if let MetricState::Value(limit) = adapter.dedicated_limit {
                    let path = format!("gpu.adapter.{index}.dedicated_limit_bytes");
                    out.push((path, limit.0 as f64));
                }
            }
        }
        // Identity travels in the snapshot, not in here: `created` is a
        // FILETIME and an `f64` cannot hold one exactly, so a rule that needs to
        // know *which* process it is reading looks at the sample, not the path.
        for process in &self.processes {
            if let MetricState::Value(bytes) = process.working_set {
                let path = format!("process.{}.working_set_bytes", process.pid);
                out.push((path, bytes.0 as f64));
            }
            if let MetricState::Value(percent) = process.cpu_percent {
                let path = format!("process.{}.cpu_percent", process.pid);
                out.push((path, f64::from(percent)));
            }
        }
        if let MetricState::Value(uptime) = self.uptime {
            out.push(("system.uptime_seconds".to_owned(), uptime as f64));
        }
        out
    }

    /// The volume mounted at `letter` (`"C:"`), if it is in this snapshot.
    pub fn volume(&self, letter: &str) -> Option<&VolumeSample> {
        self.volumes.iter().find(|v| v.letter() == letter)
    }
}

/// Every path shape [`Snapshot::metrics`] can publish, with `*` standing for one
/// key.
///
/// The list exists so a rule's `requires` — and a rules file's — can be checked
/// against what the snapshot actually emits rather than against the struct's
/// fields. A rule citing `memory.commit_used` is citing a name no consumer can
/// resolve, and that has to be catchable without a running machine.
pub const PUBLISHED_PATHS: &[&str] = &[
    "cpu.percent",
    "cpu.core.*.percent",
    "memory.percent_used",
    "memory.total_bytes",
    "memory.available_bytes",
    "memory.commit_used_bytes",
    "memory.commit_limit_bytes",
    "memory.pages_input_per_second",
    "volume.*.percent_used",
    "volume.*.free_bytes",
    "volume.*.total_bytes",
    "disk.read_bytes_per_second",
    "disk.write_bytes_per_second",
    "disk.seconds_per_transfer",
    "gpu.adapter.*.dedicated_used_bytes",
    "gpu.adapter.*.dedicated_limit_bytes",
    "process.*.working_set_bytes",
    "process.*.cpu_percent",
    "system.uptime_seconds",
];

/// Whether `path` matches a shape [`Snapshot::metrics`] publishes.
///
/// A pattern is accepted too: `volume.*.percent_used` matches itself, which is
/// what a rule's `requires` carries.
pub fn is_published_path(path: &str) -> bool {
    PUBLISHED_PATHS.iter().any(|shape| matches_shape(shape, path))
}

fn matches_shape(shape: &str, path: &str) -> bool {
    let mut shape = shape.split('.');
    let mut path = path.split('.');
    loop {
        match (shape.next(), path.next()) {
            (None, None) => return true,
            (Some(shape), Some(path)) => {
                if shape != "*" && shape != path {
                    return false;
                }
            }
            _ => return false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_published_path_matches_exactly_one_key_at_a_time() {
        assert!(is_published_path("volume.C.percent_used"));
        assert!(is_published_path("volume.*.percent_used"));
        assert!(is_published_path("cpu.core.3.percent"));
        assert!(is_published_path("process.1234.cpu_percent"));
        assert!(is_published_path("system.uptime_seconds"));

        // The names a rule might reach for and miss.
        assert!(!is_published_path("memory.commit_used"));
        assert!(!is_published_path("volume.C.percent"));
        assert!(!is_published_path("cpu.percent.extra"));
        assert!(!is_published_path(""));
        assert!(matches_shape("cpu.percent", "cpu.percent"));
        assert!(!matches_shape("cpu.*", "cpu.percent.extra"));
    }

    #[test]
    fn identity_is_in_the_sample_and_not_in_the_paths() {
        let process = process(4242, 64);
        let json = serde_json::to_string(&process).expect("a process is serialisable");
        let back: ProcessSample = serde_json::from_str(&json).expect("and deserialisable");
        // The stamp survives the round trip the history store and the JSON
        // payload both make...
        assert_eq!(back.created.value().copied(), Some(4_242_000u64), "{json}");
        // ...and is deliberately not a metric path, because an f64 cannot carry
        // a FILETIME exactly. A path that is nearly right is worse than none.
        assert!(!is_published_path("process.4242.created"));
    }

    fn volume(mount: &str, total: u64, free: u64) -> VolumeSample {
        VolumeSample {
            mount: mount.to_owned(),
            kind: VolumeKind::Fixed,
            total: MetricState::Value(Bytes(total)),
            free: MetricState::Value(Bytes(free)),
        }
    }

    #[test]
    fn a_missing_measurement_is_never_zero() {
        let unknown: MetricState<Bytes> = MetricState::Unknown(WhyUnknown::NeedsElevation);
        assert!(!unknown.is_known());
        assert_eq!(unknown.why(), Some(WhyUnknown::NeedsElevation));
        assert_eq!(unknown.value(), None);
        // The only way to get a number is to ask for one explicitly.
        let mut snapshot = Snapshot {
            seq: 1,
            taken_at: Timestamp(0),
            monotonic_ms: 0,
            cpu: CpuSample {
                percent: MetricState::Unknown(WhyUnknown::NotSampledYet),
                per_core: Vec::new(),
            },
            memory: MemorySample {
                total: MetricState::Unknown(WhyUnknown::CollectorFailed),
                available: MetricState::Unknown(WhyUnknown::CollectorFailed),
                commit_limit: MetricState::Unknown(WhyUnknown::CollectorFailed),
                commit_used: MetricState::Unknown(WhyUnknown::CollectorFailed),
                pages_input_per_second: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            },
            volumes: Vec::new(),
            disk_io: DiskIoSample::unavailable(WhyUnknown::NotCollectedYet),
            gpu: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            processes: Vec::new(),
            uptime: MetricState::Unknown(WhyUnknown::CollectorFailed),
        };
        assert!(snapshot.metrics().is_empty(), "unknown metrics must not become numbers");
        // A process row is no different: its rate is published under its pid
        // only once it has been measured, and the process that has only been
        // seen once publishes its memory and no rate at all.
        snapshot.processes = vec![process(400, 64), busy(401, 1, 3.5)];
        let metrics = snapshot.metrics();
        assert!(metrics.contains(&("process.401.cpu_percent".to_owned(), 3.5)));
        assert!(metrics.contains(&("process.400.working_set_bytes".to_owned(), 64.0 * 1024.0 * 1024.0)));
        assert!(
            metrics.iter().all(|(path, _)| path != "process.400.cpu_percent"),
            "{metrics:?}"
        );
    }

    fn process(pid: u32, megabytes: u64) -> ProcessSample {
        ProcessSample {
            pid,
            name: format!("proc{pid}.exe"),
            working_set: MetricState::Value(Bytes(megabytes * 1024 * 1024)),
            cpu_percent: MetricState::Unknown(WhyUnknown::NotSampledYet),
            // Distinct per pid, so a test about identity is not accidentally
            // passing because every process looks the same.
            created: MetricState::Value(u64::from(pid) * 1_000),
        }
    }

    fn busy(pid: u32, megabytes: u64, percent: f32) -> ProcessSample {
        ProcessSample { cpu_percent: MetricState::Value(percent), ..process(pid, megabytes) }
    }

    #[test]
    fn with_no_rate_known_the_heaviest_processes_come_first() {
        let processes = vec![process(4, 100), process(9, 900), process(2, 100)];
        let top = top_processes(processes, TOP_PROCESSES);
        let pids: Vec<u32> = top.iter().map(|p| p.pid).collect();
        // 9 is heaviest; 4 and 2 tie, and the lower pid wins, so the list is the
        // same on every run and a screenshot can be compared with a log.
        assert_eq!(pids, vec![9, 2, 4]);
    }

    #[test]
    fn a_busy_process_outranks_a_big_idle_one() {
        // 900 MB idle versus 10 MB using most of a core: the list is about what
        // is happening now, and the CPU column is how that is read.
        let top = top_processes(vec![busy(3, 900, 0.2), busy(8, 10, 87.5)], TOP_PROCESSES);
        assert_eq!(top[0].pid, 8);
        assert_eq!(top[1].pid, 3);
        // Two equally busy processes fall back to memory, then to pid.
        let top = top_processes(vec![busy(1, 10, 5.0), busy(2, 20, 5.0)], TOP_PROCESSES);
        assert_eq!(top[0].pid, 2);
        // A measured rate beats an unknown one, whatever the memory.
        let top = top_processes(vec![process(4, 5_000), busy(6, 1, 0.0)], TOP_PROCESSES);
        assert_eq!(top[0].pid, 6);
    }

    #[test]
    fn a_process_list_is_cut_to_the_limit_and_never_grows() {
        let processes: Vec<ProcessSample> = (1..=20).map(|pid| process(pid, u64::from(pid))).collect();
        assert_eq!(top_processes(processes.clone(), TOP_PROCESSES).len(), TOP_PROCESSES);
        assert_eq!(top_processes(processes.clone(), 0).len(), 0);
        assert_eq!(top_processes(processes, 100).len(), 20);
        assert!(top_processes(Vec::new(), TOP_PROCESSES).is_empty());
    }

    #[test]
    fn a_process_whose_memory_is_unknown_sorts_last_rather_than_looking_empty() {
        let mystery = ProcessSample {
            pid: 1,
            name: "protected.exe".to_owned(),
            working_set: MetricState::Unknown(WhyUnknown::NeedsElevation),
            cpu_percent: MetricState::Unknown(WhyUnknown::NotSampledYet),
            created: MetricState::Unknown(WhyUnknown::NeedsElevation),
        };
        let top = top_processes(vec![mystery, process(7, 10)], TOP_PROCESSES);
        assert_eq!(top[0].pid, 7);
        assert_eq!(top[1].pid, 1);
        assert_eq!(top[1].working_set, MetricState::Unknown(WhyUnknown::NeedsElevation));
    }

    fn adapter(instance: &str, used: u64, limit: u64) -> GpuAdapter {
        GpuAdapter {
            instance: instance.to_owned(),
            dedicated_used: MetricState::Value(Bytes(used)),
            dedicated_limit: MetricState::Value(Bytes(limit)),
        }
    }

    #[test]
    fn gpu_percentage_refuses_to_divide_by_nothing() {
        let discrete = adapter("luid_0x0_0x1_phys_0", 1_000, 4_000);
        assert_eq!(discrete.percent_used(), Some(25.0));
        // An integrated GPU owns no memory of its own; that is a fact about the
        // hardware, not a measurement, and "0 % of 0 B" is not an answer.
        let integrated = adapter("luid_0x0_0x2_phys_0", 512, 0);
        assert_eq!(integrated.percent_used(), None);
        // More used than exists (a driver accounting quirk) clamps rather than
        // reporting 140 %.
        let odd = adapter("luid_0x0_0x3_phys_0", 5_000, 4_000);
        assert_eq!(odd.percent_used(), Some(100.0));
        let unknown = GpuAdapter {
            instance: "luid_0x0_0x4_phys_0".to_owned(),
            dedicated_used: MetricState::Unknown(WhyUnknown::CollectorFailed),
            dedicated_limit: MetricState::Value(Bytes(4_000)),
        };
        assert_eq!(unknown.percent_used(), None);
    }

    #[test]
    fn the_heaviest_adapter_is_the_one_with_the_most_memory() {
        let sample = GpuSample {
            adapters: vec![
                adapter("integrated", 512, 0),
                adapter("discrete", 2_000, 8_000),
            ],
        };
        assert_eq!(sample.heaviest().map(|a| a.instance.as_str()), Some("discrete"));
        assert!(GpuSample { adapters: Vec::new() }.heaviest().is_none());
    }

    #[test]
    fn throughput_is_plotted_when_it_exists_and_absent_when_it_does_not() {
        let mut snapshot = Snapshot {
            seq: 1,
            taken_at: Timestamp(0),
            monotonic_ms: 0,
            cpu: CpuSample { percent: MetricState::Value(5.0), per_core: Vec::new() },
            memory: MemorySample {
                total: MetricState::Value(Bytes(1_000)),
                available: MetricState::Value(Bytes(900)),
                commit_limit: MetricState::Unknown(WhyUnknown::NotCollectedYet),
                commit_used: MetricState::Unknown(WhyUnknown::NotCollectedYet),
                pages_input_per_second: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            },
            volumes: Vec::new(),
            disk_io: DiskIoSample {
                read_bytes_per_second: MetricState::Value(Bytes(4_096)),
                write_bytes_per_second: MetricState::Unknown(WhyUnknown::CollectorFailed),
                avg_seconds_per_transfer: MetricState::Value(0.004),
            },
            // Nothing here is about graphics, and this test is about disk lines:
            // saying so is what keeps it from implying an empty adapter list.
            gpu: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            processes: Vec::new(),
            uptime: MetricState::Value(60),
        };
        let paths: Vec<String> = snapshot.metrics().into_iter().map(|(path, _)| path).collect();
        assert!(paths.contains(&"disk.read_bytes_per_second".to_owned()));
        // A write rate nobody measured has no line to draw; a 0 would look like
        // a quiet disk, which is a different fact.
        assert!(!paths.contains(&"disk.write_bytes_per_second".to_owned()));
        assert!(snapshot.disk_io.is_known());
        snapshot.disk_io = DiskIoSample::unavailable(WhyUnknown::NotCollectedYet);
        assert!(!snapshot.disk_io.is_known());
        assert!(!snapshot.metrics().iter().any(|(path, _)| path.starts_with("disk.")));
    }

    #[test]
    fn a_measured_core_is_plotted_and_an_unmeasured_core_is_not() {
        let mut snapshot = Snapshot {
            seq: 1,
            taken_at: Timestamp(0),
            monotonic_ms: 0,
            cpu: CpuSample {
                percent: MetricState::Value(40.0),
                per_core: vec![
                    MetricState::Value(100.0),
                    MetricState::Unknown(WhyUnknown::NotSampledYet),
                    MetricState::Value(25.0),
                ],
            },
            memory: MemorySample {
                total: MetricState::Value(Bytes(1_000)),
                available: MetricState::Value(Bytes(500)),
                commit_limit: MetricState::Unknown(WhyUnknown::NotCollectedYet),
                commit_used: MetricState::Unknown(WhyUnknown::NotCollectedYet),
                pages_input_per_second: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            },
            volumes: Vec::new(),
            disk_io: DiskIoSample::unavailable(WhyUnknown::NotCollectedYet),
            gpu: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            processes: Vec::new(),
            uptime: MetricState::Value(60),
        };
        let paths: Vec<String> = snapshot.metrics().into_iter().map(|(path, _)| path).collect();
        assert!(paths.contains(&"cpu.core.0.percent".to_owned()));
        assert!(paths.contains(&"cpu.core.2.percent".to_owned()));
        // A core that was not measured has no line to draw. Drawing 0 for it
        // would be the same picture as an idle core, and mean the opposite.
        assert!(!paths.contains(&"cpu.core.1.percent".to_owned()));
        snapshot.cpu.per_core.clear();
        assert!(!snapshot.metrics().iter().any(|(path, _)| path.starts_with("cpu.core.")));
    }

    #[test]
    fn percent_used_is_bounded_and_survives_nonsense() {
        let v = volume("C:\\", 100, 25);
        assert_eq!(v.percent_used(), MetricState::Value(75.0));
        assert_eq!(v.letter(), "C:");

        // A collector bug must not produce 250 % or a negative.
        let odd = volume("C:\\", 100, 150);
        assert_eq!(odd.percent_used(), MetricState::Value(0.0));

        // Zero total is unknown, not 100 %.
        let empty = volume("Z:\\", 0, 0);
        assert_eq!(empty.percent_used(), MetricState::Unknown(WhyUnknown::CollectorFailed));
    }

    #[test]
    fn memory_percent_carries_the_reason_it_is_missing() {
        let mut memory = MemorySample {
            total: MetricState::Unsupported(WhyUnknown::NotOnThisWindowsVersion),
            available: MetricState::Value(Bytes(1)),
            commit_limit: MetricState::Unknown(WhyUnknown::CollectorFailed),
            commit_used: MetricState::Unknown(WhyUnknown::CollectorFailed),
            pages_input_per_second: MetricState::Unknown(WhyUnknown::NotCollectedYet),
        };
        assert_eq!(
            memory.percent_used(),
            MetricState::Unsupported(WhyUnknown::NotOnThisWindowsVersion)
        );
        memory.total = MetricState::Value(Bytes(1000));
        memory.available = MetricState::Value(Bytes(250));
        assert_eq!(memory.percent_used(), MetricState::Value(75.0));
    }

    #[test]
    fn metric_paths_are_stable_and_lettered() {
        let snapshot = Snapshot {
            seq: 7,
            taken_at: Timestamp(1_700_000_000_000),
            monotonic_ms: 5,
            cpu: CpuSample { percent: MetricState::Value(12.5), per_core: Vec::new() },
            memory: MemorySample {
                total: MetricState::Value(Bytes(16_000_000_000)),
                available: MetricState::Value(Bytes(4_000_000_000)),
                commit_limit: MetricState::Value(Bytes(20_000_000_000)),
                commit_used: MetricState::Value(Bytes(8_000_000_000)),
                pages_input_per_second: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            },
            volumes: vec![volume("C:\\", 1000, 100)],
            disk_io: DiskIoSample::unavailable(WhyUnknown::NotCollectedYet),
            gpu: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            processes: Vec::new(),
            uptime: MetricState::Value(3600),
        };
        let metrics = snapshot.metrics();
        let paths: Vec<&str> = metrics.iter().map(|(p, _)| p.as_str()).collect();
        assert!(paths.contains(&"cpu.percent"));
        assert!(paths.contains(&"memory.percent_used"));
        assert!(paths.contains(&"memory.commit_used_bytes"));
        assert!(paths.contains(&"memory.commit_limit_bytes"));
        assert!(paths.contains(&"volume.C.percent_used"));
        assert!(paths.contains(&"system.uptime_seconds"));
        // The commit charge is the one memory figure a rule can cite that is not
        // a percentage, so its values are checked, not just its path.
        let metrics = snapshot.metrics();
        let commit = |path: &str| metrics.iter().find(|(p, _)| p == path).map(|(_, v)| *v);
        assert_eq!(commit("memory.commit_used_bytes"), Some(8_000_000_000.0));
        // …and an unreadable commit charge publishes nothing at all.
        let mut unknown = snapshot.clone();
        unknown.memory.commit_used = MetricState::Unknown(WhyUnknown::CollectorFailed);
        assert!(unknown.metrics().iter().all(|(p, _)| p != "memory.commit_used_bytes"));
        assert_eq!(
            snapshot.volume("C:").map(VolumeSample::percent_used),
            Some(MetricState::Value(90.0))
        );
        assert_eq!(snapshot.volume("D:"), None);
    }

    #[test]
    fn timestamps_saturate_instead_of_panicking() {
        let a = Timestamp(100);
        assert_eq!(a.plus(i64::MAX), Timestamp(i64::MAX));
        assert_eq!(Timestamp(50).since(Timestamp(100)), 0);
        assert_eq!(Timestamp(150).since(Timestamp(100)), 50);
    }

    #[test]
    fn serialization_keeps_the_reason() {
        let snapshot = Snapshot {
            seq: 1,
            taken_at: Timestamp(0),
            monotonic_ms: 0,
            cpu: CpuSample {
                percent: MetricState::Unknown(WhyUnknown::NotSampledYet),
                per_core: Vec::new(),
            },
            memory: MemorySample {
                total: MetricState::Unsupported(WhyUnknown::NotOnThisWindowsVersion),
                available: MetricState::Value(Bytes(1)),
                commit_limit: MetricState::Value(Bytes(2)),
                commit_used: MetricState::Value(Bytes(1)),
                pages_input_per_second: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            },
            volumes: vec![volume("C:\\", 4, 1)],
            disk_io: DiskIoSample::unavailable(WhyUnknown::NotCollectedYet),
            gpu: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            processes: Vec::new(),
            uptime: MetricState::Value(1),
        };
        let json = serde_json::to_string(&snapshot).unwrap();
        // The reason travels with the absence: {"state":"unknown","value":"not_sampled_yet"}.
        assert!(json.contains("\"state\":\"unknown\""), "{json}");
        assert!(json.contains("\"value\":\"not_sampled_yet\""), "{json}");
        assert!(json.contains("\"state\":\"unsupported\""), "{json}");
        let back: Snapshot = serde_json::from_str(&json).unwrap();
        assert_eq!(back, snapshot);
    }
}
