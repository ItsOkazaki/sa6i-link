// SPDX-License-Identifier: MPL-2.0
//! The machine model: what Sa6i has measured, and what it could not.
//!
//! The rule this module exists to enforce is that **a missing measurement is a
//! value, not a zero**. [`MetricState`] makes "unavailable" impossible to
//! confuse with "0 %", "0 bytes" or "no problem found" — every consumer has to
//! match on it before it can display anything.

use std::time::{SystemTime, UNIX_EPOCH};

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
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct CpuSample {
    /// Percent of total capacity, 0 to 100, averaged over the interval between
    /// this sample and the previous one.
    pub percent: MetricState<f32>,
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
        if let MetricState::Value(p) = self.memory.percent_used() {
            out.push(("memory.percent_used".to_owned(), f64::from(p)));
        }
        if let MetricState::Value(total) = self.memory.total {
            out.push(("memory.total_bytes".to_owned(), total.0 as f64));
        }
        if let MetricState::Value(available) = self.memory.available {
            out.push(("memory.available_bytes".to_owned(), available.0 as f64));
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

#[cfg(test)]
mod tests {
    use super::*;

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
        let snapshot = Snapshot {
            seq: 1,
            taken_at: Timestamp(0),
            monotonic_ms: 0,
            cpu: CpuSample { percent: MetricState::Unknown(WhyUnknown::NotSampledYet) },
            memory: MemorySample {
                total: MetricState::Unknown(WhyUnknown::CollectorFailed),
                available: MetricState::Unknown(WhyUnknown::CollectorFailed),
                commit_limit: MetricState::Unknown(WhyUnknown::CollectorFailed),
                commit_used: MetricState::Unknown(WhyUnknown::CollectorFailed),
            },
            volumes: Vec::new(),
            uptime: MetricState::Unknown(WhyUnknown::CollectorFailed),
        };
        assert!(snapshot.metrics().is_empty(), "unknown metrics must not become numbers");
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
            cpu: CpuSample { percent: MetricState::Value(12.5) },
            memory: MemorySample {
                total: MetricState::Value(Bytes(16_000_000_000)),
                available: MetricState::Value(Bytes(4_000_000_000)),
                commit_limit: MetricState::Value(Bytes(20_000_000_000)),
                commit_used: MetricState::Value(Bytes(8_000_000_000)),
            },
            volumes: vec![volume("C:\\", 1000, 100)],
            uptime: MetricState::Value(3600),
        };
        let metrics = snapshot.metrics();
        let paths: Vec<&str> = metrics.iter().map(|(p, _)| p.as_str()).collect();
        assert!(paths.contains(&"cpu.percent"));
        assert!(paths.contains(&"memory.percent_used"));
        assert!(paths.contains(&"volume.C.percent_used"));
        assert!(paths.contains(&"system.uptime_seconds"));
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
            cpu: CpuSample { percent: MetricState::Unknown(WhyUnknown::NotSampledYet) },
            memory: MemorySample {
                total: MetricState::Unsupported(WhyUnknown::NotOnThisWindowsVersion),
                available: MetricState::Value(Bytes(1)),
                commit_limit: MetricState::Value(Bytes(2)),
                commit_used: MetricState::Value(Bytes(1)),
            },
            volumes: vec![volume("C:\\", 4, 1)],
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
