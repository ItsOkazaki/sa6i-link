// SPDX-License-Identifier: MPL-2.0
//! The Sa6i intelligence core: the machine model, evidence and rules.
//!
//! This crate knows nothing about Windows, Qt, HTTP or the shell. It defines
//! what a measurement is ([`MetricState`]), what a problem is ([`Finding`] with
//! [`Evidence`]), and how a rule is allowed to decide ([`evaluate`]). Anything
//! that touches a machine implements [`Collector`]; anything that talks to a
//! model lives in the shell.
//!
//! The invariant the whole design rests on: **no finding without evidence, and
//! no number without a measurement.** Both are enforced here, in types and in
//! tests, rather than by convention in the UI.
//!
//! See `docs/architecture/INTELLIGENCE-CORE.md`.

mod budget;
mod cpu;
mod findings;
mod history;
mod model;
mod rules;
mod rules_file;
mod store;
mod summary;
mod view;

pub use budget::{CPU_SHARE, Cost, RATE_TOLERANCE, SAMPLE_SHARE, Verdict};
pub use cpu::{ProcessCpu, ProcessKey};
pub use findings::{
    Confidence, Evidence, Finding, Severity, all_clear_sentence, human_duration, render_bytes,
    render_percent,
};
pub use history::{History, HistoryError, RECORD_INTERVAL_MS};
pub use model::{
    Bytes, CpuSample, DiskIoSample, GpuAdapter, GpuSample, MemorySample, MetricState, ProcessSample,
    Snapshot, TOP_PROCESSES, Timestamp, VolumeKind, VolumeSample, WhyUnknown, top_processes,
};
pub use rules::{RULES, Rule, RuleDef, Thresholds, evaluate, evaluate_with};
pub use rules_file::{Refusal, RuleFile};
pub use store::{DEFAULT_CAPACITY, HeldWindow, SampleStore};
pub use summary::{Average, WindowSummary};
pub use view::{
    CoreBar, MonitorView, NO_VALUE, ProcessRow, SPARKLINE_POINTS, Sparkline, Tile, TileId, VolumeRow,
    monitor_view, render_rate,
};

/// One machine, sampled.
///
/// `seq` and `monotonic_ms` are supplied by the caller rather than read from a
/// clock inside the collector, so a rule's window arithmetic is testable with
/// no clock at all — and so a clock change cannot move history around.
pub trait Collector {
    /// Take one snapshot. Implementations must never panic, must never block
    /// for long (the window samples at 1 Hz), and must report unreadable
    /// metrics as [`MetricState::Unknown`] with a reason.
    fn sample(&mut self, seq: u64, monotonic_ms: u64) -> Snapshot;
}
