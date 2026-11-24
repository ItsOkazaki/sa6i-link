// SPDX-License-Identifier: MPL-2.0
//! The rule engine.
//!
//! A rule is a function from measured state to zero or one [`Finding`]. It
//! cannot take an action, cannot read the disk, cannot call a model, and cannot
//! report anything it did not measure — the signature is the policy.
//!
//! The rules are written in Rust; the numbers they decide with live in
//! [`Thresholds`], which every rule takes as an argument. Slice 1 read the
//! constants directly, which made a rule impossible to test at a second
//! threshold — and the TOML front-end in `docs/plan/M2-RULES.md` is exactly that
//! test. [`Thresholds::default()`] is what M1 shipped, to the digit.

use crate::findings::{
    Confidence, Evidence, Finding, Severity, render_bytes, render_percent,
};
use crate::model::{MemorySample, MetricState, ProcessSample, Snapshot};
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
    pub evaluate: fn(&Snapshot, &SampleStore, &Thresholds) -> Option<Finding>,
}

/// The rules this build ships, in the order the UI should show them.
pub static RULES: &[Rule] = &[
    Rule { def: CPU_SUSTAINED_HIGH, evaluate: cpu_sustained_high },
    Rule { def: CPU_ONE_CORE_PINNED, evaluate: cpu_one_core_pinned },
    Rule { def: DISK_LOW_FREE_SPACE, evaluate: disk_low_free_space },
    Rule { def: DISK_FILLING_FAST, evaluate: disk_filling_fast },
    Rule { def: MEMORY_PRESSURE, evaluate: memory_pressure },
    Rule { def: MEMORY_COMMIT_PRESSURE, evaluate: memory_commit_pressure },
    Rule { def: PROCESS_RUNAWAY_CPU, evaluate: process_runaway_cpu },
    Rule { def: PROCESS_MEMORY_GROWTH, evaluate: process_memory_growth },
    Rule { def: DISK_SLOW_TRANSFERS, evaluate: disk_slow_transfers },
    Rule { def: MEMORY_PAGING, evaluate: memory_paging },
    Rule { def: SYSTEM_LONG_UPTIME, evaluate: system_long_uptime },
];

/// Total CPU use at or above this share, and for how long.
///
/// 90 % for ten minutes. A render or a compile is this rule being right rather
/// than wrong: the machine is working as hard as it can and that is the honest
/// answer to "why is everything slow". What the rule adds is the case nobody
/// started — a stuck updater, a miner, a game left paused in the background —
/// where the graph is high and the person has no explanation for it.
const CPU_WARN_PERCENT: f32 = 90.0;
const CPU_SUSTAINED_MS: u64 = 10 * 60 * 1000;

/// One logical processor at or above this share, while the machine as a whole
/// stays under the second number, for ten minutes.
///
/// 95 % of a core while the whole machine is under 50 %: a single-threaded
/// program doing all of its work in one place. The two numbers together are what
/// makes the claim mean something. A core at 95 % on its own is any busy machine;
/// a core at 95 % while the other seven idle is one program that will take as
/// long as one thread takes, and Task Manager's overview cannot show it.
const CORE_PINNED_PERCENT: f32 = 95.0;
const CORE_PINNED_TOTAL_BELOW_PERCENT: f32 = 50.0;
const CORE_PINNED_MS: u64 = 10 * 60 * 1000;

/// Free space thresholds, as percentages of the volume.
const DISK_WARN_PERCENT: f32 = 90.0;
const DISK_CRITICAL_PERCENT: f32 = 97.0;
/// How long a volume must stay full before it is a finding. Disk use moves
/// slowly in normal work; a spike means a download, not a problem.
const DISK_SUSTAINED_MS: u64 = 10 * 60 * 1000;

/// How much free space a volume may lose, and over how long, before it is worth
/// saying.
///
/// 5 GiB in half an hour. A download, a backup or a screen recording looks exactly
/// like this and is not a fault — which is why the finding reports the rate it
/// measured and never a forecast of when the disk fills. The window is the longest
/// in the catalogue because free space moves in bursts: five gigabytes across ten
/// minutes is a large file being copied, and the same five across thirty is a disk
/// that is being written to faster than it is being read from.
const DISK_FILL_BYTES: u64 = 5 * 1024 * 1024 * 1024;
const DISK_FILL_WINDOW_MS: u64 = 30 * 60 * 1000;

/// Physical memory pressure, and how long it must last.
const MEMORY_WARN_PERCENT: f32 = 90.0;
const MEMORY_SUSTAINED_MS: u64 = 2 * 60 * 1000;

/// Commit charge, as a share of the commit limit, and how long.
///
/// Higher than the physical-memory threshold on purpose: commit includes the
/// pagefile, so a machine sitting at 90 % of it is not yet in trouble, while a
/// machine at 90 % of physical memory already is.
const COMMIT_WARN_PERCENT: f32 = 90.0;
const COMMIT_SUSTAINED_MS: u64 = 5 * 60 * 1000;

/// A process holding this share of one core, and for how long.
///
/// Percent of a core, not of the machine: a program with several busy threads can
/// read above 100, and 80 % of one core for ten minutes is a program that is not
/// going to stop on its own.
const RUNAWAY_CPU_PERCENT: f32 = 80.0;
const RUNAWAY_CPU_SUSTAINED_MS: u64 = 10 * 60 * 1000;

/// Hard faults per second that make the disk stand in for memory, and for how
/// long.
///
/// 100 pages a second for five minutes. A machine opening a program hits thousands
/// for a moment, which is fine; a machine that *stays* in the hundreds is one
/// whose working set no longer fits in RAM, and every one of those pages is a disk
/// read on the critical path.
const PAGING_PAGES_PER_SECOND: f32 = 100.0;
const PAGING_SUSTAINED_MS: u64 = 5 * 60 * 1000;

/// How long a disk transfer may take, and for how long, before the disk is the
/// problem.
///
/// 100 ms per transfer. A solid state drive answers in a fraction of a millisecond
/// and a mechanical one in a few; at a tenth of a second the disk is the queue and
/// the machine is slow at everything that touches storage, whatever the CPU graph
/// says.
const SLOW_TRANSFER_SECONDS: f32 = 0.1;
const SLOW_TRANSFER_SUSTAINED_MS: u64 = 10 * 60 * 1000;

/// How much a process may grow, and over how long, before it is a leak.
///
/// 256 MiB over half an hour: below that it is a cache filling, which is the
/// machine doing its job. The window is longer than any other rule's because a
/// leak is a trend, and half an hour is the shortest span that tells a leak from a
/// file being loaded.
const GROWTH_BYTES: u64 = 256 * 1024 * 1024;
const GROWTH_WINDOW_MS: u64 = 30 * 60 * 1000;

/// Uptime at which "have you restarted?" becomes worth saying.
const UPTIME_LONG_SECONDS: u64 = 14 * 24 * 60 * 60;

/// Every number a rule decides with, in one place.
///
/// The defaults are M1's constants, unchanged — a test says so — and a rule that
/// takes this as an argument can be run at any other set without a machine. That
/// is what the TOML front-end needs: a threshold change has to be *provable*, and
/// a rule reading a global is a rule you can only believe.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Thresholds {
    /// A local volume at or above this share of its size is nearly full.
    pub disk_warn_percent: f32,
    /// …and at or above this one, critical.
    pub disk_critical_percent: f32,
    /// How long it must stay nearly full before that is worth saying.
    pub disk_sustained_ms: u64,
    pub memory_warn_percent: f32,
    pub memory_sustained_ms: u64,
    /// Commit charge at or above this share of the commit limit is a warning.
    pub memory_commit_warn_percent: f32,
    /// …and how long it has to stay there.
    pub memory_commit_sustained_ms: u64,
    /// One process at or above this share of a core is a runaway candidate.
    pub process_cpu_percent: f32,
    /// …once it has held it this long.
    pub process_cpu_sustained_ms: u64,
    /// Memory faulting at this many pages a second…
    pub memory_pages_per_second: f32,
    /// …for this long means the working set no longer fits.
    pub memory_paging_sustained_ms: u64,
    /// A disk transfer taking at least this many seconds…
    pub disk_slow_transfer_seconds: f32,
    /// …for this long is a disk that is the reason everything is slow.
    pub disk_slow_sustained_ms: u64,
    /// A process that grew by this much…
    pub process_growth_bytes: u64,
    /// …over this long is leaking rather than working.
    pub process_growth_window_ms: u64,
    pub uptime_long_seconds: u64,
    /// The whole machine at or above this share of its CPU…
    pub cpu_warn_percent: f32,
    /// …for this long is a machine with nothing left to give.
    pub cpu_sustained_ms: u64,
    /// One core at or above this share…
    pub core_pinned_percent: f32,
    /// …while the whole machine stays below this one…
    pub core_pinned_total_below_percent: f32,
    /// …for this long is a program doing all of its work on one thread.
    pub core_pinned_ms: u64,
    /// A volume losing this many bytes of free space…
    pub disk_fill_bytes: u64,
    /// …over this long is being written to faster than it is being read from.
    pub disk_fill_window_ms: u64,
}

impl Default for Thresholds {
    fn default() -> Self {
        Self {
            disk_warn_percent: DISK_WARN_PERCENT,
            disk_critical_percent: DISK_CRITICAL_PERCENT,
            disk_sustained_ms: DISK_SUSTAINED_MS,
            memory_warn_percent: MEMORY_WARN_PERCENT,
            memory_sustained_ms: MEMORY_SUSTAINED_MS,
            memory_commit_warn_percent: COMMIT_WARN_PERCENT,
            memory_commit_sustained_ms: COMMIT_SUSTAINED_MS,
            process_cpu_percent: RUNAWAY_CPU_PERCENT,
            process_cpu_sustained_ms: RUNAWAY_CPU_SUSTAINED_MS,
            process_growth_bytes: GROWTH_BYTES,
            process_growth_window_ms: GROWTH_WINDOW_MS,
            disk_slow_transfer_seconds: SLOW_TRANSFER_SECONDS,
            disk_slow_sustained_ms: SLOW_TRANSFER_SUSTAINED_MS,
            memory_pages_per_second: PAGING_PAGES_PER_SECOND,
            memory_paging_sustained_ms: PAGING_SUSTAINED_MS,
            uptime_long_seconds: UPTIME_LONG_SECONDS,
            cpu_warn_percent: CPU_WARN_PERCENT,
            cpu_sustained_ms: CPU_SUSTAINED_MS,
            core_pinned_percent: CORE_PINNED_PERCENT,
            core_pinned_total_below_percent: CORE_PINNED_TOTAL_BELOW_PERCENT,
            core_pinned_ms: CORE_PINNED_MS,
            disk_fill_bytes: DISK_FILL_BYTES,
            disk_fill_window_ms: DISK_FILL_WINDOW_MS,
        }
    }
}

/// The machine has been at or above its CPU ceiling for ten minutes.
///
/// This is the rule everybody assumes a monitoring tool has, and the reason it is
/// worth having is narrower than it looks: a compile, a render or a game produces
/// it and the person already knows why. The case it earns is the one nobody
/// started. So the finding says what the number is and leaves the question of
/// whether it was expected to the person reading it — an alarm that calls every
/// build a fault is an alarm people stop reading.
pub const CPU_SUSTAINED_HIGH: RuleDef = RuleDef {
    id: "cpu.sustained_high",
    severity: Severity::Warning,
    confidence: Confidence::Likely,
    requires: &["cpu.percent"],
};

fn cpu_sustained_high(
    snapshot: &Snapshot,
    store: &SampleStore,
    limits: &Thresholds,
) -> Option<Finding> {
    let warn = limits.cpu_warn_percent;
    let MetricState::Value(percent) = snapshot.cpu.percent else {
        return None;
    };
    if percent < warn {
        return None;
    }
    let window = store.held_for(limits.cpu_sustained_ms, |sample| {
        sample.cpu.percent.value().is_some_and(|p| *p >= warn)
    })?;
    let mut evidence = vec![
        Evidence::new("cpu.percent", render_percent(percent))
            .threshold(render_percent(warn))
            .over(window.from_seq, window.to_seq, window.held_for_ms),
    ];
    // When the cores were measured, say where the work is. Eight cores at 90 %
    // and one at 91 % are the same total and different machines, and the second
    // one is `cpu.one_core_pinned`'s finding rather than this one.
    if let Some((index, busiest)) = busiest_core(&snapshot.cpu.per_core) {
        evidence.push(Evidence::new(
            format!("cpu.core.{index}.percent"),
            render_percent(busiest),
        ));
    }
    Some(Finding {
        id: format!("{}/system", CPU_SUSTAINED_HIGH.id),
        rule: CPU_SUSTAINED_HIGH.id.to_owned(),
        severity: CPU_SUSTAINED_HIGH.severity,
        confidence: CPU_SUSTAINED_HIGH.confidence,
        subject: "system".to_owned(),
        title: "The processor has been almost fully busy".to_owned(),
        explain: format!(
            "CPU use has been at or above {warn:.0} % for {} minutes. If you started a \
             build, a render or a game, this is that program using the machine it was given. \
             If you did not, something is working in the background, and the process list on \
             this page is where to look for it.",
            window.held_for_ms / 60_000
        ),
        evidence,
        actions: Vec::new(),
        first_seen: snapshot.taken_at,
        last_seen: snapshot.taken_at,
        snapshot_seq: snapshot.seq,
    })
}

/// One logical processor has been pinned for ten minutes while the machine as a
/// whole was quiet.
///
/// This is the finding the CPU graph cannot show: on eight cores a
/// single-threaded program at 100 % is 12 % of the machine, so the overview reads
/// "idle" while the program takes exactly as long as one thread takes. The rule
/// asks whether *a* core is pinned rather than whether the same core has been for
/// the whole window, because Windows moves a busy thread between processors
/// constantly and demanding one index would make the rule silent exactly when the
/// machine is single-thread bound.
///
/// Two honest limits. On a two-core machine a pinned core is half the machine,
/// which is over the ceiling, so the rule is quiet there rather than calling a
/// half-busy machine calm. And `process.runaway_cpu` names the program when the
/// process list can be read; this rule is what is left when it cannot.
pub const CPU_ONE_CORE_PINNED: RuleDef = RuleDef {
    id: "cpu.one_core_pinned",
    severity: Severity::Notice,
    confidence: Confidence::Likely,
    requires: &["cpu.core.*.percent", "cpu.percent"],
};

fn cpu_one_core_pinned(
    snapshot: &Snapshot,
    store: &SampleStore,
    limits: &Thresholds,
) -> Option<Finding> {
    let pinned = limits.core_pinned_percent;
    let ceiling = limits.core_pinned_total_below_percent;
    let MetricState::Value(total) = snapshot.cpu.percent else {
        return None;
    };
    // A busy machine is the other rule's finding. Two sentences about one fact is
    // how a page reads as noise.
    if total >= ceiling {
        return None;
    }
    let (index, percent) = busiest_core(&snapshot.cpu.per_core)?;
    if percent < pinned {
        return None;
    }
    let window = store.held_for(limits.core_pinned_ms, |sample| {
        let some_core = sample
            .cpu
            .per_core
            .iter()
            .any(|core| core.value().is_some_and(|p| *p >= pinned));
        some_core && sample.cpu.percent.value().is_some_and(|p| *p < ceiling)
    })?;
    Some(Finding {
        id: format!("{}/system", CPU_ONE_CORE_PINNED.id),
        rule: CPU_ONE_CORE_PINNED.id.to_owned(),
        severity: CPU_ONE_CORE_PINNED.severity,
        confidence: CPU_ONE_CORE_PINNED.confidence,
        subject: "system".to_owned(),
        title: "One processor core is doing all the work".to_owned(),
        explain: format!(
            "Core {index} has been at or above {pinned:.0} % for {} minutes while the whole \
             machine stayed under {ceiling:.0} %. That is one program using a single thread: it \
             will take as long as one thread takes, and the idle cores cannot make it faster. \
             Everything else stays responsive, which is why the overall CPU reading looks calm.",
            window.held_for_ms / 60_000
        ),
        evidence: vec![
            Evidence::new(format!("cpu.core.{index}.percent"), render_percent(percent))
                .threshold(render_percent(pinned))
                .over(window.from_seq, window.to_seq, window.held_for_ms),
            Evidence::new("cpu.percent", render_percent(total)),
        ],
        actions: Vec::new(),
        first_seen: snapshot.taken_at,
        last_seen: snapshot.taken_at,
        snapshot_seq: snapshot.seq,
    })
}

/// The busiest measured core and its index, or `None` when no core was measured.
///
/// A core that read `Unknown` is skipped rather than counted as idle: the two look
/// the same in a bar chart and mean opposite things.
fn busiest_core(per_core: &[MetricState<f32>]) -> Option<(usize, f32)> {
    per_core
        .iter()
        .enumerate()
        .filter_map(|(index, core)| core.value().map(|percent| (index, *percent)))
        .max_by(|a, b| a.1.total_cmp(&b.1))
}

/// A local volume is nearly full, and has been for ten minutes.
pub const DISK_LOW_FREE_SPACE: RuleDef = RuleDef {
    id: "disk.low_free_space",
    severity: Severity::Warning,
    confidence: Confidence::Certain,
    requires: &["volume.*.percent_used"],
};

fn disk_low_free_space(
    snapshot: &Snapshot,
    store: &SampleStore,
    limits: &Thresholds,
) -> Option<Finding> {
    let warn = limits.disk_warn_percent;
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
        if percent < warn {
            continue;
        }
        let letter = volume.letter().to_owned();
        let Some(window) = store.held_for(limits.disk_sustained_ms, move |sample| {
            sample
                .volume(&letter)
                .and_then(|v| v.percent_used().value().copied())
                .is_some_and(|p| p >= warn)
        }) else {
            continue;
        };
        if worst.as_ref().is_none_or(|(_, best, _)| percent > *best) {
            worst = Some((volume, percent, window));
        }
    }

    let (volume, percent, window) = worst?;
    let severity = if percent >= limits.disk_critical_percent {
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
             {warn:.0} % for {} minutes. Windows needs headroom for the page file, \
             updates and temp files; below about 10 % free, several things slow down.",
            window.held_for_ms / 60_000
        ),
        evidence: vec![
            Evidence::new(format!("volume.{letter}.percent_used"), render_percent(percent))
                .threshold(render_percent(warn))
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

/// A volume has lost a lot of free space in the last half hour.
///
/// This is a rate, not a level: the `disk.low_free_space` rule says a volume is
/// nearly full, this one says it is getting there quickly. Both are needed, because
/// a volume at 40 % that lost ten gigabytes in twenty minutes is the more
/// interesting of the two facts and the level rule cannot see it at all.
///
/// What it deliberately does not do is forecast. "Your disk will be full by
/// Thursday" is arithmetic on a rate that has held for half an hour, and it is
/// wrong the moment the copy finishes. The finding reports the drop and the window
/// it was measured over, and stops there.
///
/// It compares the ends of the window rather than the peak inside it: a machine
/// that filled ten gigabytes and then deleted them is a machine that is not
/// filling, and the endpoint difference is the only number that says so.
pub const DISK_FILLING_FAST: RuleDef = RuleDef {
    id: "disk.filling_fast",
    severity: Severity::Notice,
    confidence: Confidence::Likely,
    requires: &["volume.*.free_bytes"],
};

fn disk_filling_fast(
    snapshot: &Snapshot,
    store: &SampleStore,
    limits: &Thresholds,
) -> Option<Finding> {
    let window_ms = limits.disk_fill_window_ms;
    // A window the history does not span cannot be answered, and the start of
    // history is not the start of the window.
    if store.span_ms() < window_ms {
        return None;
    }
    let start = snapshot.monotonic_ms.saturating_sub(window_ms);
    let first = store.samples().find(|sample| sample.monotonic_ms >= start)?;

    // The fullest loss, one volume at a time: three findings that say the same
    // thing is noise, and the user acts on the fastest one first.
    let mut worst: Option<(&crate::model::VolumeSample, u64, u64, u64)> = None;
    for volume in &snapshot.volumes {
        if !volume.kind.is_local_storage() {
            continue;
        }
        let Some(now) = volume.free.value().map(|free| free.0) else {
            continue;
        };
        // A volume that was not mounted when the window opened has no "before",
        // and a missing before is not a zero drop.
        let Some(before) = first
            .volume(volume.letter())
            .and_then(|earlier| earlier.free.value().map(|free| free.0))
        else {
            continue;
        };
        let lost = before.saturating_sub(now);
        if lost < limits.disk_fill_bytes {
            continue;
        }
        if worst.as_ref().is_none_or(|(_, best, _, _)| lost > *best) {
            worst = Some((volume, lost, before, now));
        }
    }

    let (volume, lost, before, now) = worst?;
    let letter = volume.letter().to_owned();
    let minutes = snapshot.monotonic_ms.saturating_sub(first.monotonic_ms) / 60_000;
    let total = match volume.total {
        MetricState::Value(total) => render_bytes(total.0),
        _ => "an unknown size".to_owned(),
    };
    Some(Finding {
        id: format!("{}/{letter}", DISK_FILLING_FAST.id),
        rule: DISK_FILLING_FAST.id.to_owned(),
        severity: DISK_FILLING_FAST.severity,
        confidence: DISK_FILLING_FAST.confidence,
        subject: letter.clone(),
        title: format!("Drive {letter} is losing free space quickly"),
        explain: format!(
            "Drive {letter} has {} free of {total}, {} less than {minutes} minutes ago. \
             Something is writing: a download, a backup, a recording, or a program filling \
             a log. That is a fact about the last half hour, not a prediction - if the copy \
             finishes, the number stops moving, and if it does not, the volume is what runs \
             out first.",
            render_bytes(now),
            render_bytes(lost)
        ),
        evidence: vec![
            Evidence::new(format!("volume.{letter}.free_bytes"), render_bytes(now))
                .threshold(format!("{} lost", render_bytes(lost)))
                .over(
                    first.seq,
                    snapshot.seq,
                    snapshot.monotonic_ms.saturating_sub(first.monotonic_ms),
                ),
            Evidence::new(format!("volume.{letter}.free_bytes"), render_bytes(before))
                .threshold(format!("{minutes} minutes ago")),
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

fn memory_pressure(
    snapshot: &Snapshot,
    store: &SampleStore,
    limits: &Thresholds,
) -> Option<Finding> {
    let warn = limits.memory_warn_percent;
    let MetricState::Value(percent) = snapshot.memory.percent_used() else {
        return None;
    };
    if percent < warn {
        return None;
    }
    let window = store.held_for(limits.memory_sustained_ms, |sample| {
        sample
            .memory
            .percent_used()
            .value()
            .copied()
            .is_some_and(|p| p >= warn)
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
             above {warn:.0} % for {} minutes. Windows is paging, which is what \
             makes switching between apps feel slow.",
            window.held_for_ms / 60_000
        ),
        evidence: vec![
            Evidence::new("memory.percent_used", render_percent(percent))
                .threshold(render_percent(warn))
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

/// Commit charge has been close to the commit limit for five minutes.
///
/// This is the rule that answers a complaint Task Manager makes hard to see:
/// "it says out of memory and there is plenty of RAM". Commit charge counts
/// every byte the system has promised to a program, including the pagefile, so
/// it can run out while physical memory looks comfortable. Physical memory
/// pressure is a different finding, with a lower threshold, because the two
/// fail differently: paging slows a machine down, running out of commit makes
/// allocations fail.
pub const MEMORY_COMMIT_PRESSURE: RuleDef = RuleDef {
    id: "memory.commit_pressure",
    severity: Severity::Warning,
    confidence: Confidence::Likely,
    requires: &["memory.commit_used_bytes", "memory.commit_limit_bytes"],
};

/// Commit charge as a share of the limit, or `None`.
///
/// A zero limit is not "0 % used": it is a machine that did not answer, and
/// dividing by it would either invent a finding or hide one. Every caller treats
/// `None` as "no opinion".
fn commit_percent(memory: &MemorySample) -> Option<f32> {
    let used = memory.commit_used.value()?.0;
    let limit = memory.commit_limit.value()?.0;
    if limit == 0 {
        return None;
    }
    // Not clamped at 100: a machine past its commit limit is more interesting
    // than one at it, and hiding that would be the same mistake as rendering an
    // unmeasured rate as zero.
    Some((used as f64 / limit as f64 * 100.0) as f32)
}

fn memory_commit_pressure(
    snapshot: &Snapshot,
    store: &SampleStore,
    limits: &Thresholds,
) -> Option<Finding> {
    let warn = limits.memory_commit_warn_percent;
    let percent = commit_percent(&snapshot.memory)?;
    if percent < warn {
        return None;
    }
    let window = store.held_for(limits.memory_commit_sustained_ms, |sample| {
        commit_percent(&sample.memory).is_some_and(|p| p >= warn)
    })?;
    // Both are values: `commit_percent` above returned one, which it only does
    // when both sides are readable.
    let used = snapshot.memory.commit_used.value()?;
    let limit = snapshot.memory.commit_limit.value()?;
    let warn_bytes = (limit.0 as f64 * f64::from(warn) / 100.0) as u64;
    Some(Finding {
        id: format!("{}/system", MEMORY_COMMIT_PRESSURE.id),
        rule: MEMORY_COMMIT_PRESSURE.id.to_owned(),
        severity: MEMORY_COMMIT_PRESSURE.severity,
        confidence: MEMORY_COMMIT_PRESSURE.confidence,
        subject: "system".to_owned(),
        title: "Committed memory is close to the limit".to_owned(),
        explain: format!(
            "{} of {} commit is in use ({percent:.1} %) and it has been above {warn:.0} % for {} \
             minutes. Commit charge counts every byte the system has promised, including the \
             pagefile, so it can reach the limit while RAM looks free - and then allocations fail \
             and programs close with an out-of-memory error.",
            render_bytes(used.0),
            render_bytes(limit.0),
            window.held_for_ms / 60_000
        ),
        evidence: vec![
            Evidence::new("memory.commit_used_bytes", render_bytes(used.0))
                .threshold(render_bytes(warn_bytes))
                .over(window.from_seq, window.to_seq, window.held_for_ms),
            Evidence::new("memory.commit_limit_bytes", render_bytes(limit.0)),
        ],
        actions: Vec::new(),
        first_seen: snapshot.taken_at,
        last_seen: snapshot.taken_at,
        snapshot_seq: snapshot.seq,
    })
}

/// One process has held most of a core for ten minutes.
///
/// Identity is the whole difficulty here, and it is why the creation stamp had to
/// reach the snapshot first: Windows hands a pid to a new process as soon as the
/// old one exits, so "pid 4242 has been busy for ten minutes" is only true if it
/// was the same process the whole time. A recycled pid is a different subject,
/// and the fixture that proves it stays quiet when the stamp changes mid-window.
pub const PROCESS_RUNAWAY_CPU: RuleDef = RuleDef {
    id: "process.runaway_cpu",
    severity: Severity::Notice,
    confidence: Confidence::Likely,
    requires: &["process.*.cpu_percent"],
};

fn process_runaway_cpu(
    snapshot: &Snapshot,
    store: &SampleStore,
    limits: &Thresholds,
) -> Option<Finding> {
    let warn = limits.process_cpu_percent;
    // One process at a time: a finding per busy process on a machine doing heavy
    // work would be a wall of text that says "something is compiling".
    let mut worst: Option<(&ProcessSample, f32, crate::store::HeldWindow)> = None;
    for process in &snapshot.processes {
        let MetricState::Value(percent) = process.cpu_percent else {
            continue;
        };
        if percent < warn {
            continue;
        }
        // No stamp, no claim: without identity this rule would attribute one
        // program's ten minutes to the program that inherited its pid.
        let Some(created) = process.created.value().copied() else {
            continue;
        };
        let pid = process.pid;
        let Some(window) = store.held_for(limits.process_cpu_sustained_ms, move |sample| {
            sample.processes.iter().any(|candidate| {
                candidate.pid == pid
                    && candidate.created.value().copied() == Some(created)
                    && candidate
                        .cpu_percent
                        .value()
                        .is_some_and(|percent| *percent >= warn)
            })
        }) else {
            continue;
        };
        if worst.as_ref().is_none_or(|(_, best, _)| percent > *best) {
            worst = Some((process, percent, window));
        }
    }

    let (process, percent, window) = worst?;
    let pid = process.pid;
    let name = if process.name.is_empty() {
        format!("pid {pid}")
    } else {
        process.name.clone()
    };
    let working_set = match process.working_set.value() {
        Some(bytes) => render_bytes(bytes.0),
        None => "an unknown amount of memory".to_owned(),
    };
    Some(Finding {
        id: format!("{}/{pid}", PROCESS_RUNAWAY_CPU.id),
        rule: PROCESS_RUNAWAY_CPU.id.to_owned(),
        severity: PROCESS_RUNAWAY_CPU.severity,
        confidence: PROCESS_RUNAWAY_CPU.confidence,
        subject: format!("{name} ({pid})"),
        title: format!("{name} is holding a core"),
        explain: format!(
            "{name} (pid {pid}) has used {percent:.0} % of a core for {} minutes while holding \
             {working_set}. A process that never comes down is usually a stuck update, a script \
             that is not finishing, or a window repainting in a loop.",
            window.held_for_ms / 60_000
        ),
        evidence: vec![
            Evidence::new(format!("process.{pid}.cpu_percent"), render_percent(percent))
                .threshold(render_percent(warn))
                .over(window.from_seq, window.to_seq, window.held_for_ms),
            Evidence::new(format!("process.{pid}.working_set_bytes"), working_set),
        ],
        actions: Vec::new(),
        first_seen: snapshot.taken_at,
        last_seen: snapshot.taken_at,
        snapshot_seq: snapshot.seq,
    })
}

/// A process has grown by a quarter of a gigabyte in half an hour.
///
/// Growth is measured against the same process at the start of the window, which
/// is why the creation stamp matters here as much as it does upstairs: "pid 5150
/// grew from 300 MiB to 700 MiB" is only true if it was the same pid 5150 at both
/// ends. A process that appeared ten minutes ago has no half-hour to answer for,
/// and says nothing.
pub const PROCESS_MEMORY_GROWTH: RuleDef = RuleDef {
    id: "process.memory_growth",
    severity: Severity::Notice,
    confidence: Confidence::Likely,
    requires: &["process.*.working_set_bytes"],
};

fn process_memory_growth(
    snapshot: &Snapshot,
    store: &SampleStore,
    limits: &Thresholds,
) -> Option<Finding> {
    let window_ms = limits.process_growth_window_ms;
    // A window the history does not span cannot be answered; treating the start of
    // history as the start of the window is how a spike becomes a trend.
    if store.span_ms() < window_ms {
        return None;
    }
    let start = snapshot.monotonic_ms.saturating_sub(window_ms);
    // The first snapshot inside the window, which is the one a process has to
    // appear in to have been there for the whole of it.
    let first = store.samples().find(|sample| sample.monotonic_ms >= start)?;

    let mut worst: Option<(&ProcessSample, u64, u64, u64)> = None;
    for process in &snapshot.processes {
        let Some(after) = process.working_set.value().map(|bytes| bytes.0) else {
            continue;
        };
        let Some(created) = process.created.value().copied() else {
            continue;
        };
        let Some(before) = first
            .processes
            .iter()
            .find(|candidate| {
                candidate.pid == process.pid
                    && candidate.created.value().copied() == Some(created)
                    && candidate.working_set.value().is_some()
            })
            .and_then(|candidate| candidate.working_set.value().map(|bytes| bytes.0))
        else {
            continue;
        };
        let grown = after.saturating_sub(before);
        if grown < limits.process_growth_bytes {
            continue;
        }
        if worst.as_ref().is_none_or(|(_, best, _, _)| grown > *best) {
            worst = Some((process, before, after, grown));
        }
    }

    let (process, before, after, grown) = worst?;
    let pid = process.pid;
    let name = if process.name.is_empty() {
        format!("pid {pid}")
    } else {
        process.name.clone()
    };
    let minutes = snapshot.monotonic_ms.saturating_sub(first.monotonic_ms) / 60_000;
    Some(Finding {
        id: format!("{}/{pid}", PROCESS_MEMORY_GROWTH.id),
        rule: PROCESS_MEMORY_GROWTH.id.to_owned(),
        severity: PROCESS_MEMORY_GROWTH.severity,
        confidence: PROCESS_MEMORY_GROWTH.confidence,
        subject: format!("{name} ({pid})"),
        title: format!("{name} keeps taking more memory"),
        explain: format!(
            "{name} (pid {pid}) has grown from {} to {} over {minutes} minutes - {} more, and it \
             has not given any of it back. Steady growth that never comes down is a leak: the \
             program will eventually be the reason this machine pages.",
            render_bytes(before),
            render_bytes(after),
            render_bytes(grown)
        ),
        evidence: vec![
            Evidence::new(format!("process.{pid}.working_set_bytes"), render_bytes(after))
                .threshold(render_bytes(before))
                .over(
                    first.seq,
                    snapshot.seq,
                    snapshot.monotonic_ms.saturating_sub(first.monotonic_ms),
                ),
        ],
        actions: Vec::new(),
        first_seen: snapshot.taken_at,
        last_seen: snapshot.taken_at,
        snapshot_seq: snapshot.seq,
    })
}

/// Disk transfers have taken a tenth of a second or more for ten minutes.
///
/// This is the rule that answers "the machine is slow but nothing is using the
/// CPU". It is also the one that has to be careful about zero: `Avg. Disk
/// sec/Transfer` reads 0 on an idle disk, and an idle disk is not a fast one -
/// so zero is never a finding, and an idle stretch inside the window breaks the
/// claim rather than averaging into it.
pub const DISK_SLOW_TRANSFERS: RuleDef = RuleDef {
    id: "disk.slow_transfers",
    severity: Severity::Warning,
    confidence: Confidence::Likely,
    requires: &["disk.seconds_per_transfer"],
};

fn disk_slow_transfers(
    snapshot: &Snapshot,
    store: &SampleStore,
    limits: &Thresholds,
) -> Option<Finding> {
    let slow = limits.disk_slow_transfer_seconds;
    let MetricState::Value(seconds) = snapshot.disk_io.avg_seconds_per_transfer else {
        return None;
    };
    // Zero is "no transfers", which is an idle disk. An idle disk is not a slow
    // one, and a rule that fired on it would fire on every quiet machine.
    if seconds <= 0.0 || seconds < slow {
        return None;
    }
    let window = store.held_for(limits.disk_slow_sustained_ms, |sample| {
        sample
            .disk_io
            .avg_seconds_per_transfer
            .value()
            .is_some_and(|seconds| *seconds >= slow)
    })?;
    let millis = seconds * 1000.0;
    Some(Finding {
        id: format!("{}/system", DISK_SLOW_TRANSFERS.id),
        rule: DISK_SLOW_TRANSFERS.id.to_owned(),
        severity: DISK_SLOW_TRANSFERS.severity,
        confidence: DISK_SLOW_TRANSFERS.confidence,
        subject: "system".to_owned(),
        title: "The disk is taking a long time per transfer".to_owned(),
        explain: format!(
            "Each disk transfer has averaged {millis:.0} ms for {} minutes, against the {:.0} ms \
             a healthy disk stays under. At this rate the disk is the queue: opening a file, \
             saving a document and starting a program all wait on it, which looks like a slow \
             machine while the CPU sits idle. A failing disk, a queue that never drains and a \
             backup running at full speed all look like this.",
            window.held_for_ms / 60_000,
            slow * 1000.0
        ),
        evidence: vec![
            Evidence::new("disk.seconds_per_transfer", format!("{millis:.1} ms"))
                .threshold(format!("{:.0} ms", slow * 1000.0))
                .over(window.from_seq, window.to_seq, window.held_for_ms),
        ],
        actions: Vec::new(),
        first_seen: snapshot.taken_at,
        last_seen: snapshot.taken_at,
        snapshot_seq: snapshot.seq,
    })
}

/// The disk has been making up for full memory for five minutes.
///
/// The companion to `disk.slow_transfers`, and they are not the same finding: a
/// slow disk is slow for its own reasons, while this one says memory is too small
/// for what is running and the disk is what pays. A machine can have this without
/// a slow disk (a fast SSD absorbs it and the machine merely feels sluggish) and a
/// slow disk without this.
pub const MEMORY_PAGING: RuleDef = RuleDef {
    id: "memory.paging",
    severity: Severity::Warning,
    confidence: Confidence::Likely,
    requires: &["memory.pages_input_per_second"],
};

fn memory_paging(
    snapshot: &Snapshot,
    store: &SampleStore,
    limits: &Thresholds,
) -> Option<Finding> {
    let busy = limits.memory_pages_per_second;
    let MetricState::Value(pages) = snapshot.memory.pages_input_per_second else {
        return None;
    };
    // Zero hard faults is a machine with room to spare, not a fault-free disk.
    if pages <= 0.0 || pages < busy {
        return None;
    }
    let window = store.held_for(limits.memory_paging_sustained_ms, |sample| {
        sample
            .memory
            .pages_input_per_second
            .value()
            .is_some_and(|pages| *pages >= busy)
    })?;
    Some(Finding {
        id: format!("{}/system", MEMORY_PAGING.id),
        rule: MEMORY_PAGING.id.to_owned(),
        severity: MEMORY_PAGING.severity,
        confidence: MEMORY_PAGING.confidence,
        subject: "system".to_owned(),
        title: "The disk is doing memory's work".to_owned(),
        explain: format!(
            "{pages:.0} pages a second have been read back from disk for {} minutes. Those are \
             hard faults: memory that had to be written out and fetched again, so the disk is \
             standing in for RAM. Everything that touches that memory waits on the disk, and on a \
             mechanical drive the machine feels far worse than this number looks. More memory, or \
             fewer programs open at once, is the fix.",
            window.held_for_ms / 60_000
        ),
        evidence: vec![
            Evidence::new("memory.pages_input_per_second", format!("{pages:.0} pages/s"))
                .threshold(format!("{busy:.0} pages/s"))
                .over(window.from_seq, window.to_seq, window.held_for_ms),
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

fn system_long_uptime(
    snapshot: &Snapshot,
    _store: &SampleStore,
    limits: &Thresholds,
) -> Option<Finding> {
    let MetricState::Value(seconds) = snapshot.uptime else {
        return None;
    };
    if seconds < limits.uptime_long_seconds {
        return None;
    }
    let days = seconds / 86_400;
    // The evidence names the threshold the rule was given, not the one it was
    // written with: a finding that cites a number it did not use is a lie in the
    // one place the product promises there are none.
    let threshold = format!("{} days", limits.uptime_long_seconds / 86_400);
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
        .threshold(threshold)],
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
    evaluate_with(snapshot, store, &Thresholds::default())
}

/// The same, at numbers of the caller's choosing.
///
/// This is the whole reason [`Thresholds`] exists: the golden fixtures can be run
/// at M1's numbers *and* at a second set, so the front-end that will eventually
/// supply those numbers can be believed rather than trusted.
pub fn evaluate_with(
    snapshot: &Snapshot,
    store: &SampleStore,
    limits: &Thresholds,
) -> Vec<Finding> {
    let mut findings: Vec<Finding> = RULES
        .iter()
        .filter_map(|rule| (rule.evaluate)(snapshot, store, limits))
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
    use crate::model::{
        Bytes, CpuSample, DiskIoSample, MemorySample, ProcessSample, VolumeKind, VolumeSample,
        WhyUnknown,
    };

    /// A machine that is fine: 20 % CPU, half the memory, half of C:.
    fn healthy(seq: u64, monotonic_ms: u64) -> Snapshot {
        Snapshot {
            seq,
            taken_at: crate::model::Timestamp(seq as i64 * 1000),
            monotonic_ms,
            cpu: CpuSample { percent: MetricState::Value(20.0), per_core: Vec::new() },
            memory: MemorySample {
                total: MetricState::Value(Bytes(16 * 1_000_000_000)),
                available: MetricState::Value(Bytes(8 * 1_000_000_000)),
                commit_limit: MetricState::Value(Bytes(24 * 1_000_000_000)),
                commit_used: MetricState::Value(Bytes(9 * 1_000_000_000)),
                pages_input_per_second: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            },
            volumes: vec![VolumeSample {
                mount: "C:\\".to_owned(),
                kind: VolumeKind::Fixed,
                total: MetricState::Value(Bytes(500 * 1_000_000_000)),
                free: MetricState::Value(Bytes(250 * 1_000_000_000)),
            }],
            disk_io: DiskIoSample::unavailable(WhyUnknown::NotCollectedYet),
            gpu: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            processes: Vec::new(),
            uptime: MetricState::Value(3600),
        }
    }

    fn with_disk_used(snapshot: &mut Snapshot, percent: f32) {
        let total = 500 * 1_000_000_000u64;
        let free = ((100.0 - percent) / 100.0 * total as f32) as u64;
        snapshot.volumes[0].total = MetricState::Value(Bytes(total));
        snapshot.volumes[0].free = MetricState::Value(Bytes(free));
    }

    fn process_of(pid: u32, name: &str, created: u64, percent: f32, megabytes: u64) -> ProcessSample {
        ProcessSample {
            pid,
            name: name.to_owned(),
            working_set: MetricState::Value(Bytes(megabytes * 1_000_000)),
            cpu_percent: MetricState::Value(percent),
            created: MetricState::Value(created),
        }
    }

    fn busy_process(pid: u32, name: &str, created: u64, percent: f32) -> ProcessSample {
        process_of(pid, name, created, percent, 200)
    }

    fn with_commit(snapshot: &mut Snapshot, percent: f32) {
        let limit = 24 * 1_000_000_000u64;
        let used = (percent / 100.0 * limit as f32) as u64;
        snapshot.memory.commit_limit = MetricState::Value(Bytes(limit));
        snapshot.memory.commit_used = MetricState::Value(Bytes(used));
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
    fn a_zero_commit_limit_is_no_opinion_rather_than_a_division() {
        // A machine that reports a zero limit has not answered the question. The
        // rule must keep quiet: 0 % would be a lie, and 100 % would be a worse
        // one.
        let store = series(600, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            snap.memory.commit_limit = MetricState::Value(Bytes(0));
            snap.memory.commit_used = MetricState::Value(Bytes(1_000));
            snap
        });
        assert!(findings_of(&store).is_empty());
    }

    #[test]
    fn commit_pressure_needs_five_minutes_and_then_says_so() {
        // Four minutes of a high commit charge is a program starting, not a
        // machine running out of promises.
        let brief = series(600, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_commit(&mut snap, if s + 1 > 360 { 95.0 } else { 40.0 });
            snap
        });
        assert!(findings_of(&brief).is_empty(), "four minutes is not five");

        let sustained = series(360, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_commit(&mut snap, 95.0);
            snap
        });
        let findings = findings_of(&sustained);
        assert_eq!(findings.len(), 1, "{findings:?}");
        assert_eq!(findings[0].rule, "memory.commit_pressure");
        // Both cited paths are ones `metrics()` publishes, which is what makes
        // the evidence checkable after the fact.
        let cited: Vec<&str> = findings[0].evidence.iter().map(|e| e.metric.as_str()).collect();
        assert!(cited.contains(&"memory.commit_used_bytes"), "{cited:?}");
        assert!(cited.contains(&"memory.commit_limit_bytes"), "{cited:?}");
    }

    #[test]
    fn commit_pressure_moves_with_its_threshold() {
        let store = series(360, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_commit(&mut snap, 60.0);
            snap
        });
        let snapshot = store.latest().expect("samples").clone();
        assert!(evaluate(&snapshot, &store).is_empty(), "60 % is not 90 %");
        let strict = Thresholds { memory_commit_warn_percent: 55.0, ..Thresholds::default() };
        let findings = evaluate_with(&snapshot, &store, &strict);
        assert_eq!(findings.len(), 1, "{findings:?}");
        assert_eq!(findings[0].rule, "memory.commit_pressure");
    }

    #[test]
    fn ten_minutes_of_one_core_is_one_finding() {
        let store = series(660, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            snap.processes = vec![busy_process(4242, "render.exe", 1_000, 96.0)];
            snap
        });
        let findings = findings_of(&store);
        assert_eq!(findings.len(), 1, "{findings:?}");
        assert_eq!(findings[0].rule, "process.runaway_cpu");
        assert_eq!(findings[0].subject, "render.exe (4242)");
        assert_eq!(findings[0].id, "process.runaway_cpu/4242");
        let cited: Vec<&str> = findings[0].evidence.iter().map(|e| e.metric.as_str()).collect();
        assert!(cited.contains(&"process.4242.cpu_percent"), "{cited:?}");
    }

    #[test]
    fn a_reused_pid_is_two_processes_not_ten_minutes() {
        // The fixture that only passes because identity reaches the snapshot: the
        // same pid and the same name throughout, a new creation stamp halfway.
        let store = series(600, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            let created = if s < 300 { 1_000 } else { 2_000 };
            snap.processes = vec![busy_process(4242, "render.exe", created, 96.0)];
            snap
        });
        assert!(
            findings_of(&store).is_empty(),
            "two five-minute processes are not one ten-minute one"
        );
    }

    #[test]
    fn a_process_without_a_stamp_is_not_accused() {
        let store = series(900, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            let mut process = busy_process(4242, "render.exe", 1_000, 96.0);
            process.created = MetricState::Unknown(WhyUnknown::NeedsElevation);
            snap.processes = vec![process];
            snap
        });
        assert!(findings_of(&store).is_empty());
    }

    #[test]
    fn a_leak_is_measured_against_the_same_process_half_an_hour_ago() {
        let store = series(1_860, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            let megabytes = if s < 900 { 300 } else { 700 };
            snap.processes = vec![process_of(5150, "sync.exe", 1_000, 5.0, megabytes)];
            snap
        });
        let findings = findings_of(&store);
        assert_eq!(findings.len(), 1, "{findings:?}");
        assert_eq!(findings[0].rule, "process.memory_growth");
        assert_eq!(findings[0].subject, "sync.exe (5150)");
        // The evidence cites the size now and the size then, over the window the
        // growth was measured across.
        let evidence = &findings[0].evidence[0];
        assert_eq!(evidence.metric, "process.5150.working_set_bytes");
        // Half an hour of evidence, not one sample of it.
        assert!(evidence.held_for_ms >= 30 * 60 * 1000, "{evidence:?}");
        assert!(evidence.from_seq < evidence.to_seq, "{evidence:?}");
    }

    #[test]
    fn a_process_that_started_inside_the_window_has_nothing_to_answer_for() {
        let store = series(1_860, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            if s >= 1_200 {
                snap.processes = vec![process_of(5150, "sync.exe", 1_000, 5.0, 900)];
            }
            snap
        });
        assert!(
            findings_of(&store).is_empty(),
            "ten minutes of history is not half an hour of growth"
        );
    }

    #[test]
    fn an_idle_disk_is_not_a_slow_one() {
        // `Avg. Disk sec/Transfer` reads 0 when nothing is transferred. Zero is a
        // fact about an idle machine, not an infinitely fast one, and it must
        // never turn into a finding.
        let store = series(1_200, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            snap.disk_io.avg_seconds_per_transfer = MetricState::Value(0.0);
            snap
        });
        assert!(findings_of(&store).is_empty());
    }

    #[test]
    fn a_tenth_of_a_second_per_transfer_for_ten_minutes_is_a_finding() {
        let store = series(660, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            snap.disk_io.avg_seconds_per_transfer = MetricState::Value(0.18);
            snap
        });
        let findings = findings_of(&store);
        assert_eq!(findings.len(), 1, "{findings:?}");
        assert_eq!(findings[0].rule, "disk.slow_transfers");
        assert_eq!(findings[0].evidence[0].metric, "disk.seconds_per_transfer");
        assert_eq!(findings[0].evidence[0].observed, "180.0 ms");
    }

    #[test]
    fn paging_is_faults_that_stay_high_never_zero() {
        let busy = series(360, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            snap.memory.pages_input_per_second = MetricState::Value(150.0);
            snap
        });
        let findings = findings_of(&busy);
        assert_eq!(findings.len(), 1, "{findings:?}");
        assert_eq!(findings[0].rule, "memory.paging");
        assert_eq!(findings[0].evidence[0].metric, "memory.pages_input_per_second");

        // A machine with room to spare faults nothing, and zero pages is a
        // reading about the machine, not a rate about the disk.
        let quiet = series(360, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            snap.memory.pages_input_per_second = MetricState::Value(0.0);
            snap
        });
        assert!(findings_of(&quiet).is_empty());
    }

    /// A machine with the cores measured, which is what the CPU rules need.
    fn with_cores(snapshot: &mut Snapshot, total: f32, cores: &[f32]) {
        snapshot.cpu.percent = MetricState::Value(total);
        snapshot.cpu.per_core = cores.iter().map(|percent| MetricState::Value(*percent)).collect();
    }

    /// A volume with an exact number of free bytes, for the rate rule.
    fn with_disk_free(snapshot: &mut Snapshot, free_bytes: u64) {
        let total = 500 * 1024 * 1024 * 1024u64;
        snapshot.volumes[0].total = MetricState::Value(Bytes(total));
        snapshot.volumes[0].free = MetricState::Value(Bytes(free_bytes));
    }

    const GIB: u64 = 1024 * 1024 * 1024;

    #[test]
    fn a_disk_losing_five_gibibytes_in_half_an_hour_is_a_finding() {
        // Ten GiB gone across forty minutes, with the window's start inside the
        // part where it was already dropping.
        let store = series(2_400, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            let free = if s < 1_200 { 200 * GIB } else { 190 * GIB };
            with_disk_free(&mut snap, free);
            snap
        });
        let findings = findings_of(&store);
        let fill = findings
            .iter()
            .find(|finding| finding.rule == DISK_FILLING_FAST.id)
            .unwrap_or_else(|| panic!("ten gibibytes in forty minutes: {findings:?}"));
        assert_eq!(fill.subject, "C:");
        assert_eq!(fill.severity, Severity::Notice);
        assert_eq!(fill.evidence[0].metric, "volume.C.free_bytes");
        assert!(
            fill.evidence[0].threshold.as_deref() == Some("10.0 GB lost"),
            "{:?}",
            fill.evidence[0]
        );
        // Half an hour of evidence, not one sample of it.
        assert_eq!(fill.evidence[0].held_for_ms, 30 * 60 * 1000);
        assert!(fill.evidence[0].from_seq < fill.evidence[0].to_seq, "{:?}", fill.evidence[0]);
    }

    #[test]
    fn a_disk_that_filled_and_was_cleaned_up_inside_the_window_is_quiet() {
        // Ten gibibytes went, then came back. Comparing the ends of the window is
        // the whole point: nothing was lost over the half hour that counts.
        let store = series(2_400, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            let free = if (900..1_500).contains(&s) { 190 * GIB } else { 200 * GIB };
            with_disk_free(&mut snap, free);
            snap
        });
        assert!(findings_of(&store).is_empty(), "a cleanup is not a leak");
    }

    #[test]
    fn a_disk_under_the_line_is_not_filling_fast() {
        // 4 GiB in forty minutes: a large file, copied. Held long past the window.
        let store = series(2_400, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            let free = if s < 1_200 { 200 * GIB } else { 196 * GIB };
            with_disk_free(&mut snap, free);
            snap
        });
        assert!(findings_of(&store).is_empty());
    }

    #[test]
    fn a_half_hour_of_history_is_not_enough_to_measure_a_half_hour() {
        // The same ten gibibytes, in twenty minutes: the window is not spanned, so
        // the answer is "no opinion" rather than "not filling".
        let store = series(1_200, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_disk_free(&mut snap, if s < 600 { 200 * GIB } else { 190 * GIB });
            snap
        });
        assert!(findings_of(&store).is_empty());
    }

    #[test]
    fn ten_minutes_at_the_ceiling_is_a_finding_and_a_spike_is_not() {
        // A minute of it is a build; ten is the window.
        let brief = series(500, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            snap.cpu.percent = MetricState::Value(if s >= 420 { 94.0 } else { 20.0 });
            snap
        });
        assert!(findings_of(&brief).is_empty(), "80 seconds is not ten minutes");

        let sustained = series(660, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_cores(&mut snap, 94.0, &[94.0, 90.0, 91.0, 92.0, 93.0, 90.5, 91.5, 92.5]);
            snap
        });
        let findings = findings_of(&sustained);
        assert_eq!(findings.len(), 1, "{findings:?}");
        assert_eq!(findings[0].rule, CPU_SUSTAINED_HIGH.id);
        assert_eq!(findings[0].subject, "system");
        assert_eq!(findings[0].evidence[0].metric, "cpu.percent");
        assert!(findings[0].evidence[0].sentence().contains("10 minutes"), "{:?}", findings[0].evidence[0]);
        // The busiest core rides along, so the reader can see whether the load was
        // spread over the machine or sitting in one place.
        assert_eq!(findings[0].evidence[1].metric, "cpu.core.0.percent");
    }

    #[test]
    fn a_pinned_core_is_found_where_the_overview_looks_calm() {
        let store = series(660, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_cores(&mut snap, 22.0, &[98.0, 11.0, 12.0, 9.0, 13.0, 10.0, 11.0, 12.0]);
            snap
        });
        let findings = findings_of(&store);
        assert_eq!(findings.len(), 1, "the pair must not both fire: {findings:?}");
        assert_eq!(findings[0].rule, CPU_ONE_CORE_PINNED.id);
        assert_eq!(findings[0].severity, Severity::Notice);
        assert_eq!(findings[0].evidence[0].metric, "cpu.core.0.percent");
        // The total is cited too: "one core at 98 % while the machine is at 22 %"
        // is the whole claim, and half of it would be a different finding.
        assert_eq!(findings[0].evidence[1].metric, "cpu.percent");
    }

    #[test]
    fn a_machine_busy_on_every_core_is_not_a_pinned_one() {
        // The pair partitions the space: all cores busy is the whole-machine
        // finding, and reporting a pinned core as well would be two sentences
        // about one fact.
        let store = series(660, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_cores(&mut snap, 96.0, &[96.0; 8]);
            snap
        });
        let findings = findings_of(&store);
        assert_eq!(findings.len(), 1, "{findings:?}");
        assert_eq!(findings[0].rule, CPU_SUSTAINED_HIGH.id);
    }

    #[test]
    fn a_core_one_point_under_the_line_is_not_pinned() {
        // 94 % for twelve minutes: held well past the window and still not the
        // claim, which is what makes the window and the threshold two decisions.
        let store = series(720, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_cores(&mut snap, 22.0, &[94.0, 11.0, 12.0, 9.0, 13.0, 10.0, 11.0, 12.0]);
            snap
        });
        assert!(findings_of(&store).is_empty());
    }

    #[test]
    fn cores_that_were_not_measured_are_not_idle_ones() {
        // `per_core` empty is a machine whose cores nobody read. The rule has no
        // opinion, and in particular it does not read the blank as "all idle".
        let store = series(660, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            snap.cpu.percent = MetricState::Value(22.0);
            snap
        });
        assert!(findings_of(&store).is_empty());
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
    fn the_defaults_are_the_numbers_m1_shipped() {
        // A refactor that quietly moved a threshold would change nothing in the
        // fixtures if the fixtures were regenerated with it. This is the guard.
        let limits = Thresholds::default();
        assert_eq!(limits.disk_warn_percent, DISK_WARN_PERCENT);
        assert_eq!(limits.disk_critical_percent, DISK_CRITICAL_PERCENT);
        assert_eq!(limits.disk_sustained_ms, DISK_SUSTAINED_MS);
        assert_eq!(limits.memory_warn_percent, MEMORY_WARN_PERCENT);
        assert_eq!(limits.memory_sustained_ms, MEMORY_SUSTAINED_MS);
        assert_eq!(limits.uptime_long_seconds, UPTIME_LONG_SECONDS);
    }

    #[test]
    fn a_rule_runs_at_the_numbers_it_is_given() {
        // The same 91 % volume for the same ten minutes, twice: at M1's numbers,
        // and with the warning line moved above it.
        let store = series(700, |s| {
            let mut snap = healthy(s + 1, s * 1000);
            with_disk_used(&mut snap, 91.0);
            snap
        });
        let snapshot = store.latest().expect("samples").clone();
        assert!(
            evaluate_with(&snapshot, &store, &Thresholds::default())
                .iter()
                .any(|f| f.rule == DISK_LOW_FREE_SPACE.id)
        );
        let strict = Thresholds { disk_warn_percent: 95.0, ..Thresholds::default() };
        assert!(
            evaluate_with(&snapshot, &store, &strict).is_empty(),
            "a 95 % line is above a 91 % volume"
        );

        // A machine up for three and a half days, with the "restart?" line moved
        // to three days: the finding has to cite the number it used, not the one
        // the rule was written with.
        let mut short = healthy(1, 0);
        short.uptime = MetricState::Value(3 * 86_400 + 12 * 3_600);
        let store = series(1, |_| short.clone());
        let three_days = Thresholds { uptime_long_seconds: 3 * 86_400, ..Thresholds::default() };
        let findings = evaluate_with(&short, &store, &three_days);
        let uptime = findings
            .iter()
            .find(|f| f.rule == SYSTEM_LONG_UPTIME.id)
            .expect("three and a half days passes a three-day line");
        assert!(
            uptime.evidence.iter().any(|e| e.threshold.as_deref() == Some("3 days")),
            "{:?}",
            uptime.evidence
        );
        // At M1's fourteen days the same machine says nothing.
        assert!(evaluate_with(&short, &store, &Thresholds::default()).is_empty());
    }

    #[test]
    fn every_rule_declares_what_it_needs() {
        for rule in RULES {
            assert!(!rule.def.id.is_empty());
            assert!(rule.def.id.contains('.'), "{} should be dotted", rule.def.id);
            assert!(!rule.def.requires.is_empty(), "{} declares no inputs", rule.def.id);
        }
    }

    #[test]
    fn every_declared_input_is_a_path_a_snapshot_publishes() {
        // The other half of the sentence: a rule may not require evidence that
        // `metrics()` will never emit. Without this, `requires` is a comment.
        for rule in RULES {
            for path in rule.def.requires {
                assert!(
                    crate::model::is_published_path(path),
                    "{} requires {path}, which no snapshot publishes",
                    rule.def.id
                );
            }
        }
    }
}
