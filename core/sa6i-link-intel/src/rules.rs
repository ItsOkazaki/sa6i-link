// SPDX-License-Identifier: MPL-2.0
//! The rule engine.
//!
//! A rule is a function from measured state to zero or one [`Finding`]. It
//! cannot take an action, cannot read the disk, cannot call a model, and cannot
//! report anything it did not measure — the signature is the policy.
//!
//! Slice 1 writes the rules in Rust with their thresholds as constants, so each
//! one is a named, reviewable thing with fixtures. The TOML front-end described
//! in `docs/architecture/INTELLIGENCE-CORE.md` §5 compiles into the same
//! [`RuleDef`] plus predicate, so adding it later does not change this contract.

use crate::findings::{
    Confidence, Evidence, Finding, Severity, render_bytes, render_percent,
};
use crate::model::{MetricState, Snapshot};
use crate::store::SampleStore;

/// What a rule declares about itself.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RuleDef {
    /// Stable dotted id, e.g. `"disk.low_free_space"`.
    pub id: &'static str,
    pub severity: Severity,
    pub confidence: Confidence,
    /// Which measurements it needs. A rule whose inputs are all unavailable
    /// does not run, and does not claim the machine is fine.
    pub requires: &'static [&'static str],
}

/// A rule: its declaration and its evaluation.
#[derive(Debug, Clone, Copy)]
pub struct Rule {
    pub def: RuleDef,
    /// Returns a finding, or `None` when the condition does not hold.
    pub evaluate: fn(&Snapshot, &SampleStore) -> Option<Finding>,
}

/// The rules this build ships, in the order the UI should show them.
pub static RULES: &[Rule] = &[
    Rule { def: DISK_LOW_FREE_SPACE, evaluate: disk_low_free_space },
    Rule { def: MEMORY_PRESSURE, evaluate: memory_pressure },
    Rule { def: SYSTEM_LONG_UPTIME, evaluate: system_long_uptime },
];

/// Free space thresholds, as percentages of the volume.
const DISK_WARN_PERCENT: f32 = 90.0;
const DISK_CRITICAL_PERCENT: f32 = 97.0;
/// How long a volume must stay full before it is a finding. Disk use moves
/// slowly in normal work; a spike means a download, not a problem.
const DISK_SUSTAINED_MS: u64 = 10 * 60 * 1000;

/// Physical memory pressure, and how long it must last.
const MEMORY_WARN_PERCENT: f32 = 90.0;
const MEMORY_SUSTAINED_MS: u64 = 2 * 60 * 1000;

/// Uptime at which "have you restarted?" becomes worth saying.
const UPTIME_LONG_SECONDS: u64 = 14 * 24 * 60 * 60;

/// A local volume is nearly full, and has been for ten minutes.
pub const DISK_LOW_FREE_SPACE: RuleDef = RuleDef {
    id: "disk.low_free_space",
    severity: Severity::Warning,
    confidence: Confidence::Certain,
    requires: &["volume.*.percent_used"],
};

fn disk_low_free_space(snapshot: &Snapshot, store: &SampleStore) -> Option<Finding> {
    // The worst volume that has been full for the whole window. One volume at a
    // time: three findings that say the same thing is noise, and the user acts
    // on the fullest one first.
    let mut worst: Option<(&crate::model::VolumeSample, f32, crate::store::HeldWindow)> = None;
    for volume in &snapshot.volumes {
        if !volume.kind.is_local_storage() {
            continue;
        }
        let MetricState::Value(percent) = volume.percent_used() else {
            continue;
        };
        if percent < DISK_WARN_PERCENT {
            continue;
        }
        let letter = volume.letter().to_owned();
        let Some(window) = store.held_for(DISK_SUSTAINED_MS, move |sample| {
            sample
                .volume(&letter)
                .and_then(|v| v.percent_used().value().copied())
                .is_some_and(|p| p >= DISK_WARN_PERCENT)
        }) else {
            continue;
        };
        if worst.as_ref().is_none_or(|(_, best, _)| percent > *best) {
            worst = Some((volume, percent, window));
        }
    }

    let (volume, percent, window) = worst?;
    let severity = if percent >= DISK_CRITICAL_PERCENT {
        Severity::Critical
    } else {
        DISK_LOW_FREE_SPACE.severity
    };
    let free = match volume.free {
        MetricState::Value(free) => render_bytes(free.0),
        _ => "an unknown amount".to_owned(),
    };
    let total = match volume.total {
        MetricState::Value(total) => render_bytes(total.0),
        _ => "an unknown size".to_owned(),
    };
    let letter = volume.letter().to_owned();
    Some(Finding {
        id: format!("{}/{}", DISK_LOW_FREE_SPACE.id, letter),
        rule: DISK_LOW_FREE_SPACE.id.to_owned(),
        severity,
        confidence: DISK_LOW_FREE_SPACE.confidence,
        subject: letter.clone(),
        title: format!("Drive {letter} is almost full"),
        explain: format!(
            "{free} free of {total} ({percent:.1} % used) and it has been above \
             {DISK_WARN_PERCENT:.0} % for {} minutes. Windows needs headroom for the page file, \
             updates and temp files; below about 10 % free, several things slow down.",
            window.held_for_ms / 60_000
        ),
        evidence: vec![
            Evidence::new(format!("volume.{letter}.percent_used"), render_percent(percent))
                .threshold(render_percent(DISK_WARN_PERCENT))
                .over(window.from_seq, window.to_seq, window.held_for_ms),
            Evidence::new(
                format!("volume.{letter}.free_bytes"),
                match volume.free {
                    MetricState::Value(free) => render_bytes(free.0),
                    _ => "unavailable".to_owned(),
                },
            ),
        ],
        actions: vec!["clean.open_native_scan".to_owned()],
        first_seen: snapshot.taken_at,
        last_seen: snapshot.taken_at,
        snapshot_seq: snapshot.seq,
    })
}

/// Physical memory has been nearly exhausted for two minutes.
pub const MEMORY_PRESSURE: RuleDef = RuleDef {
    id: "memory.pressure",
    severity: Severity::Notice,
    confidence: Confidence::Likely,
    requires: &["memory.percent_used"],
};

fn memory_pressure(snapshot: &Snapshot, store: &SampleStore) -> Option<Finding> {
    let MetricState::Value(percent) = snapshot.memory.percent_used() else {
        return None;
    };
    if percent < MEMORY_WARN_PERCENT {
        return None;
    }
    let window = store.held_for(MEMORY_SUSTAINED_MS, |sample| {
        sample
            .memory
            .percent_used()
            .value()
            .copied()
            .is_some_and(|p| p >= MEMORY_WARN_PERCENT)
    })?;
    let available = match snapshot.memory.available {
        MetricState::Value(bytes) => render_bytes(bytes.0),
        _ => "an unknown amount".to_owned(),
    };
    Some(Finding {
        id: format!("{}/system", MEMORY_PRESSURE.id),
        rule: MEMORY_PRESSURE.id.to_owned(),
        severity: MEMORY_PRESSURE.severity,
        confidence: MEMORY_PRESSURE.confidence,
        subject: "system".to_owned(),
        title: "Memory is almost used up".to_owned(),
        explain: format!(
            "{percent:.1} % of physical memory is in use ({available} available) and it has been \
             above {MEMORY_WARN_PERCENT:.0} % for {} minutes. Windows is paging, which is what \
             makes switching between apps feel slow.",
            window.held_for_ms / 60_000
        ),
        evidence: vec![
            Evidence::new("memory.percent_used", render_percent(percent))
                .threshold(render_percent(MEMORY_WARN_PERCENT))
                .over(window.from_seq, window.to_seq, window.held_for_ms),
            Evidence::new(
                "memory.available_bytes",
                match snapshot.memory.available {
                    MetricState::Value(bytes) => render_bytes(bytes.0),
                    _ => "unavailable".to_owned(),
                },
            ),
        ],
        actions: Vec::new(),
        first_seen: snapshot.taken_at,
        last_seen: snapshot.taken_at,
        snapshot_seq: snapshot.seq,
    })
}

/// The machine has not been restarted in a fortnight.
pub const SYSTEM_LONG_UPTIME: RuleDef = RuleDef {
    id: "system.long_uptime",
    severity: Severity::Info,
    confidence: Confidence::Certain,
    requires: &["system.uptime_seconds"],
};

fn system_long_uptime(snapshot: &Snapshot, _store: &SampleStore) -> Option<Finding> {
    let MetricState::Value(seconds) = snapshot.uptime else {
        return None;
    };
    if seconds < UPTIME_LONG_SECONDS {
        return None;
    }
    let days = seconds / 86_400;
    Some(Finding {
        id: format!("{}/system", SYSTEM_LONG_UPTIME.id),
        rule: SYSTEM_LONG_UPTIME.id.to_owned(),
        severity: SYSTEM_LONG_UPTIME.severity,
        confidence: SYSTEM_LONG_UPTIME.confidence,
        subject: "system".to_owned(),
        title: format!("Up for {days} days"),
        explain: format!(
            "This PC has been running for {days} days. Pending updates, leaked memory and driver \
             state accumulate; a restart clears them. Nothing is broken, this is just worth doing."
        ),
        evidence: vec![Evidence::new(
            "system.uptime_seconds",
            format!("{days} days"),
        )
        .threshold("14 days")],
        actions: Vec::new(),
        first_seen: snapshot.taken_at,
        last_seen: snapshot.taken_at,
        snapshot_seq: snapshot.seq,
    })
}

/// Run every rule against the newest snapshot and its history.
///
/// Findings without evidence are dropped rather than shown: `is_supported()` is
/// a hard gate, not a style check.
pub fn evaluate(snapshot: &Snapshot, store: &SampleStore) -> Vec<Finding> {
    let mut findings: Vec<Finding> = RULES
        .iter()
        .filter_map(|rule| (rule.evaluate)(snapshot, store))
        .filter(|finding| {
            if finding.is_supported() {
                true
            } else {
                tracing::warn!(rule = finding.rule, "dropped a finding with no evidence");
                false
            }
        })
        .collect();
    // Worst first; then by id so two runs are ordered identically.
    findings.sort_by(|a, b| b.severity.cmp(&a.severity).then_with(|| a.id.cmp(&b.id)));
    findings
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Bytes, CpuSample, MemorySample, VolumeKind, VolumeSample, WhyUnknown};

    /// A machine that is fine: 20 % CPU, half the memory, half of C:.
    fn healthy(seq: u64, monotonic_ms: u64) -> Snapshot {
        Snapshot {
            seq,
            taken_at: crate::model::Timestamp(seq as i64 * 1000),
            monotonic_ms,
            cpu: CpuSample { percent: MetricState::Value(20.0) },
            memory: MemorySample {
                total: MetricState::Value(Bytes(16 * 1_000_000_000)),
                available: MetricState::Value(Bytes(8 * 1_000_000_000)),
                commit_limit: MetricState::Value(Bytes(24 * 1_000_000_000)),
                commit_used: MetricState::Value(Bytes(9 * 1_000_000_000)),
            },
            volumes: vec![VolumeSample {
                mount: "C:\\".to_owned(),
                kind: VolumeKind::Fixed,
                total: MetricState::Value(Bytes(500 * 1_000_000_000)),
                free: MetricState::Value(Bytes(250 * 1_000_000_000)),
            }],
            uptime: MetricState::Value(3600),
        }
    }

    fn with_disk_used(snapshot: &mut Snapshot, percent: f32) {
        let total = 500 * 1_000_000_000u64;
        let free = ((100.0 - percent) / 100.0 * total as f32) as u64;
        snapshot.volumes[0].total = MetricState::Value(Bytes(total));
        snapshot.volumes[0].free = MetricState::Value(Bytes(free));
    }

    /// `last_second + 1` samples at 1 Hz, so a window of N seconds is exactly
    /// covered.
    fn series(last_second: u64, mut sample: impl FnMut(u64) -> Snapshot) -> SampleStore {
        let mut store = SampleStore::with_capacity(1024 * 1024);
        for second in 0..=last_second {
            store.push(sample(second));
        }
        store
    }

    fn findings_of(store: &SampleStore) -> Vec<Finding> {
        let snapshot = store.latest().expect("a store with samples").clone();
        evaluate(&snapshot, store)
    }

    #[test]
    fn a_healthy_machine_produces_nothing() {
        let store = series(3600, |s| healthy(s + 1, s * 1000));
        assert!(findings_of(&store).is_empty());
    }

    #[test]
    fn a_full_disk_needs_ten_minutes_before_it_is_a_finding() {
        // Two minutes of a 95 % volume is not a trend.
        let brief = series(120, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_disk_used(&mut snap, 95.0);
            snap
        });
        assert!(findings_of(&brief).is_empty(), "two minutes is not a trend");

        // Ten minutes of it is.
        let sustained = series(700, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_disk_used(&mut snap, 95.0);
            snap
        });
        let findings = findings_of(&sustained);
        let disk = findings
            .iter()
            .find(|f| f.rule == DISK_LOW_FREE_SPACE.id)
            .expect("a volume full for ten minutes is a finding");
        assert_eq!(disk.subject, "C:");
        assert_eq!(disk.severity, Severity::Warning);
        assert!(disk.explain.contains("95.0 %"), "{}", disk.explain);
        assert_eq!(disk.evidence.len(), 2);
        assert!(
            disk.evidence[0].sentence().contains("10 minutes"),
            "{:?}",
            disk.evidence[0]
        );
    }

    #[test]
    fn a_nearly_empty_disk_is_critical_not_just_a_warning() {
        let store = series(700, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_disk_used(&mut snap, 98.5);
            snap
        });
        let disk = findings_of(&store)
            .into_iter()
            .find(|f| f.rule == DISK_LOW_FREE_SPACE.id)
            .unwrap();
        assert_eq!(disk.severity, Severity::Critical);
    }

    #[test]
    fn a_volume_without_a_reading_is_silent_rather_than_guessed() {
        let store = series(700, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            snap.volumes[0].free = MetricState::Unknown(WhyUnknown::CollectorFailed);
            snap
        });
        assert!(findings_of(&store).is_empty());
    }

    #[test]
    fn network_drives_are_not_the_users_problem() {
        let store = series(700, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_disk_used(&mut snap, 99.0);
            snap.volumes[0].kind = VolumeKind::Network;
            snap
        });
        assert!(findings_of(&store).is_empty());
    }

    #[test]
    fn the_worst_volume_is_the_one_reported() {
        let store = series(700, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_disk_used(&mut snap, 92.0);
            snap.volumes.push(VolumeSample {
                mount: "D:\\".to_owned(),
                kind: VolumeKind::Fixed,
                total: MetricState::Value(Bytes(1_000_000_000_000)),
                free: MetricState::Value(Bytes(10_000_000_000)),
            });
            snap
        });
        let disk: Vec<Finding> = findings_of(&store)
            .into_iter()
            .filter(|f| f.rule == DISK_LOW_FREE_SPACE.id)
            .collect();
        assert_eq!(disk.len(), 1, "one finding per rule, not one per volume");
        assert_eq!(disk[0].subject, "D:");
    }

    #[test]
    fn memory_pressure_needs_two_minutes() {
        let store = series(200, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            snap.memory.available = MetricState::Value(Bytes(500 * 1_000_000));
            snap
        });
        let memory = findings_of(&store)
            .into_iter()
            .find(|f| f.rule == MEMORY_PRESSURE.id)
            .expect("200 seconds above 90 % is pressure");
        assert_eq!(memory.severity, Severity::Notice);
        assert_eq!(memory.confidence, Confidence::Likely);
    }

    #[test]
    fn long_uptime_is_information_not_an_alarm() {
        let mut store = SampleStore::with_capacity(8);
        let mut snap = healthy(1, 0);
        snap.uptime = MetricState::Value(20 * 86_400);
        store.push(snap.clone());
        let uptime = evaluate(&snap, &store)
            .into_iter()
            .find(|f| f.rule == SYSTEM_LONG_UPTIME.id)
            .unwrap();
        assert_eq!(uptime.severity, Severity::Info);
        assert!(uptime.title.contains("20 days"), "{}", uptime.title);
    }

    #[test]
    fn findings_are_ordered_worst_first_and_stable() {
        let store = series(700, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_disk_used(&mut snap, 99.0);
            snap.uptime = MetricState::Value(30 * 86_400);
            snap
        });
        let findings = findings_of(&store);
        assert!(findings.len() >= 2);
        assert_eq!(findings[0].severity, Severity::Critical);
        let again = findings_of(&store);
        assert_eq!(
            findings.iter().map(|f| f.id.as_str()).collect::<Vec<_>>(),
            again.iter().map(|f| f.id.as_str()).collect::<Vec<_>>()
        );
    }

    #[test]
    fn every_rule_declares_what_it_needs() {
        for rule in RULES {
            assert!(!rule.def.id.is_empty());
            assert!(rule.def.id.contains('.'), "{} should be dotted", rule.def.id);
            assert!(!rule.def.requires.is_empty(), "{} declares no inputs", rule.def.id);
        }
    }
}
