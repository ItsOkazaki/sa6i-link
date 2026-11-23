// SPDX-License-Identifier: MPL-2.0
//! What the Monitor page shows, decided before anything draws it.
//!
//! The page itself is Qt: tiles, bars, a line. This module is the part that has
//! an opinion — what each tile says, which number is big, what the line does
//! when a sample is missing — so it can be tested without a screen and so the
//! QML has no arithmetic to get wrong.
//!
//! Two rules carried over from the model, kept here where the rendering could
//! still break them:
//!
//! - A tile with no reading says so, in words, and draws an empty track. It
//!   never shows `0`.
//! - A moment that was never sampled is a gap in the line, not a point at the
//!   bottom. A dropped sample and an idle machine look identical otherwise.

use serde::Serialize;

use crate::findings::{all_clear_sentence, render_bytes, render_percent};
use crate::model::{
    Bytes, DiskIoSample, GpuSample, MemorySample, MetricState, ProcessSample, Snapshot, Timestamp,
    VolumeKind, VolumeSample, WhyUnknown,
};

/// How many samples a sparkline holds: one minute at the 1 Hz sampling rate.
pub const SPARKLINE_POINTS: usize = 60;

/// What is drawn when there is no number.
pub const NO_VALUE: &str = "—";

/// Bytes per second, in the units Windows uses.
pub fn render_rate(bytes_per_second: u64) -> String {
    format!("{}/s", render_bytes(bytes_per_second))
}

fn clamp_fraction(percent: f32) -> f32 {
    (percent / 100.0).clamp(0.0, 1.0)
}

/// Which number a tile shows.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TileId {
    Cpu,
    Memory,
    Disk,
    Gpu,
}

impl TileId {
    /// Stable id for QML keys and for tests.
    pub fn id(self) -> &'static str {
        match self {
            Self::Cpu => "cpu",
            Self::Memory => "memory",
            Self::Disk => "disk",
            Self::Gpu => "gpu",
        }
    }

    /// The word above the number.
    pub fn label(self) -> &'static str {
        match self {
            Self::Cpu => "CPU",
            Self::Memory => "Memory",
            Self::Disk => "Disk",
            Self::Gpu => "GPU",
        }
    }
}

/// One tile on the Overview.
///
/// `value` and `note` are finished strings: the page never formats a number.
/// When `missing` is set the tile has no reading, `value` is [`NO_VALUE`], and
/// `note` is the reason in plain words.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Tile {
    pub id: TileId,
    pub label: &'static str,
    /// The big number, already worded: `"42.1 %"`, or [`NO_VALUE`].
    pub value: String,
    /// How much of a ring or bar to fill, 0 to 1. `None` leaves the track empty.
    pub fraction: Option<f32>,
    /// The line under the number: a fact, or why there is no fact.
    pub note: String,
    /// The reason there is no reading; `None` when the tile holds one.
    pub missing: Option<WhyUnknown>,
}

impl Tile {
    fn missing(id: TileId, why: WhyUnknown) -> Self {
        Self {
            id,
            label: id.label(),
            value: NO_VALUE.to_owned(),
            fraction: None,
            note: why.explain().to_owned(),
            missing: Some(why),
        }
    }
}

/// A line of measurements over time, newest last.
///
/// A `None` is a moment that was never measured. It stays a gap through
/// [`Sparkline::normalized`], so the drawing can leave a hole rather than
/// invent a value.
#[derive(Debug, Clone, PartialEq, Default, Serialize)]
#[serde(transparent)]
pub struct Sparkline {
    values: Vec<Option<f32>>,
}

impl Sparkline {
    /// An empty line.
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a sample, dropping the oldest beyond [`SPARKLINE_POINTS`].
    pub fn push(&mut self, value: Option<f32>) {
        self.values.push(value);
        let excess = self.values.len().saturating_sub(SPARKLINE_POINTS);
        if excess > 0 {
            self.values.drain(..excess);
        }
    }

    /// The samples, oldest first.
    pub fn values(&self) -> &[Option<f32>] {
        &self.values
    }

    pub fn len(&self) -> usize {
        self.values.len()
    }

    pub fn is_empty(&self) -> bool {
        self.values.is_empty()
    }

    /// How many samples are gaps.
    pub fn gaps(&self) -> usize {
        self.values.iter().filter(|value| value.is_none()).count()
    }

    /// The newest reading, skipping gaps.
    pub fn latest(&self) -> Option<f32> {
        self.values.iter().rev().find_map(|value| *value)
    }

    /// Each sample as 0 to 1 of `ceiling`, with the gaps left in place.
    pub fn normalized(&self, ceiling: f32) -> Vec<Option<f32>> {
        if ceiling <= 0.0 {
            return vec![None; self.values.len()];
        }
        self.values.iter().map(|value| value.map(|v| (v / ceiling).clamp(0.0, 1.0))).collect()
    }

    fn from_states(states: impl IntoIterator<Item = MetricState<f32>>) -> Self {
        let mut line = Self::new();
        for state in states {
            line.push(state.value().copied());
        }
        line
    }
}

/// One logical processor, as a bar.
#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CoreBar {
    pub index: usize,
    /// `None` when that core was not measured — the bar draws empty, not idle.
    pub percent: Option<f32>,
}

/// One row of the process table.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProcessRow {
    pub pid: u32,
    pub name: String,
    /// Working set, worded. [`NO_VALUE`] when it could not be read.
    pub memory: String,
    /// Percent of installed memory, when both numbers are known.
    pub share: Option<f32>,
    /// Percent of one core since the previous sample, when this process has been
    /// seen twice. `null` — not 0 — for a process that is new to the list or
    /// whose CPU could not be read.
    pub cpu: Option<f32>,
    pub known: bool,
}

/// One row of the volume list.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct VolumeRow {
    /// `"C:"` for the mount `"C:\\"`.
    pub mount: String,
    /// `"fixed"`, `"removable"`, `"network"`, `"optical"`, `"ram"`, `"unknown"`.
    pub kind: &'static str,
    /// Percent in use, for a bar. `None` draws an empty track.
    pub used_percent: Option<f32>,
    /// Free of total, worded, or why not.
    pub detail: String,
    pub missing: Option<WhyUnknown>,
}

/// Everything the Monitor page needs for one frame.
///
/// This is also the wire format: the Qt host serializes it to JSON once a
/// second, so the page never receives a number it has to format itself.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MonitorView {
    /// The snapshot this was built from.
    pub seq: u64,
    pub taken_at: Timestamp,
    pub tiles: Vec<Tile>,
    /// CPU use, newest last, gaps where a sample is missing.
    ///
    /// The numbers are **percentages, 0–100** — not fractions. The wire stays in
    /// the unit a person reads and a log records; a widget that draws a 0–1
    /// height divides by 100 itself, which is where a flat line at the top came
    /// from the first time this was wired up.
    pub cpu: Sparkline,
    /// Memory use, same unit and same gaps.
    pub memory: Sparkline,
    pub cores: Vec<CoreBar>,
    pub processes: Vec<ProcessRow>,
    pub volumes: Vec<VolumeRow>,
    /// How many findings the rules made from this sample. The findings
    /// themselves, and their evidence, are M2's surface.
    pub findings: usize,
    /// One sentence for the top of the page.
    pub summary: String,
}

/// Build the page from the newest snapshot and the samples before it.
///
/// `recent` is oldest first and may be short or empty; the lines hold exactly
/// what was measured, so a gap in the history stays a gap in the line.
/// `findings` is how many findings the rules produced from `snapshot`.
pub fn monitor_view(snapshot: &Snapshot, recent: &[Snapshot], findings: usize) -> MonitorView {
    MonitorView {
        seq: snapshot.seq,
        taken_at: snapshot.taken_at,
        tiles: vec![
            cpu_tile(snapshot),
            memory_tile(&snapshot.memory),
            disk_tile(&snapshot.disk_io),
            gpu_tile(&snapshot.gpu),
        ],
        cpu: Sparkline::from_states(recent.iter().map(|sample| sample.cpu.percent)),
        memory: Sparkline::from_states(recent.iter().map(|sample| sample.memory.percent_used())),
        cores: snapshot
            .cpu
            .per_core
            .iter()
            .enumerate()
            .map(|(index, core)| CoreBar { index, percent: core.value().copied() })
            .collect(),
        processes: snapshot
            .processes
            .iter()
            .map(|process| process_row(process, snapshot.memory.total.value().copied()))
            .collect(),
        volumes: snapshot.volumes.iter().map(volume_row).collect(),
        findings,
        summary: summary_line(snapshot, findings),
    }
}

fn cpu_tile(snapshot: &Snapshot) -> Tile {
    let state = snapshot.cpu.percent;
    let Some(percent) = state.value().copied() else {
        return Tile::missing(TileId::Cpu, state.why().unwrap_or(WhyUnknown::CollectorFailed));
    };
    Tile {
        id: TileId::Cpu,
        label: TileId::Cpu.label(),
        value: render_percent(percent),
        fraction: Some(clamp_fraction(percent)),
        note: cores_note(&snapshot.cpu.per_core),
        missing: None,
    }
}

/// `"8 cores, busiest 96.2 %"`, and how many were not measured if any were not.
fn cores_note(per_core: &[MetricState<f32>]) -> String {
    if per_core.is_empty() {
        return "cores not measured".to_owned();
    }
    let cores = per_core.len();
    let noun = if cores == 1 { "core" } else { "cores" };
    let measured: Vec<f32> = per_core.iter().filter_map(|core| core.value().copied()).collect();
    let unmeasured = cores - measured.len();
    let Some(busiest) = measured.iter().copied().reduce(f32::max) else {
        return format!("{cores} {noun}, none measured");
    };
    let tail = match unmeasured {
        0 => String::new(),
        1 => " (1 not measured)".to_owned(),
        n => format!(" ({n} not measured)"),
    };
    format!("{cores} {noun}, busiest {}{tail}", render_percent(busiest))
}

fn memory_tile(memory: &MemorySample) -> Tile {
    let state = memory.percent_used();
    let Some(percent) = state.value().copied() else {
        return Tile::missing(TileId::Memory, state.why().unwrap_or(WhyUnknown::CollectorFailed));
    };
    let note = match (memory.total.value(), memory.available.value()) {
        (Some(total), Some(available)) => {
            let used = total.0.saturating_sub(available.0);
            format!("{} of {} in use", render_bytes(used), render_bytes(total.0))
        }
        // The percentage itself needs both numbers, so this is unreachable in
        // practice; saying less is still better than inventing a total.
        _ => "physical memory in use".to_owned(),
    };
    Tile {
        id: TileId::Memory,
        label: TileId::Memory.label(),
        value: render_percent(percent),
        fraction: Some(clamp_fraction(percent)),
        note,
        missing: None,
    }
}

fn disk_tile(io: &DiskIoSample) -> Tile {
    match (io.read_bytes_per_second.value(), io.write_bytes_per_second.value()) {
        (Some(read), Some(write)) => Tile {
            id: TileId::Disk,
            label: TileId::Disk.label(),
            value: render_rate(read.0.saturating_add(write.0)),
            // Throughput has no ceiling worth faking a bar against.
            fraction: None,
            note: format!("{} read, {} written", render_rate(read.0), render_rate(write.0)),
            missing: None,
        },
        _ => Tile::missing(
            TileId::Disk,
            io.read_bytes_per_second
                .why()
                .or_else(|| io.write_bytes_per_second.why())
                .unwrap_or(WhyUnknown::CollectorFailed),
        ),
    }
}

fn gpu_tile(gpu: &MetricState<GpuSample>) -> Tile {
    let sample = match gpu {
        MetricState::Value(sample) => sample,
        MetricState::Unknown(why) | MetricState::Unsupported(why) => {
            return Tile::missing(TileId::Gpu, *why);
        }
    };
    let Some(adapter) = sample.heaviest() else {
        return Tile::missing(TileId::Gpu, WhyUnknown::CollectorFailed);
    };
    let used = adapter.dedicated_used.value().copied();
    let limit = adapter.dedicated_limit.value().copied();
    let (Some(used), Some(limit)) = (used, limit) else {
        let why = adapter
            .dedicated_used
            .why()
            .or_else(|| adapter.dedicated_limit.why())
            .unwrap_or(WhyUnknown::CollectorFailed);
        return Tile::missing(TileId::Gpu, why);
    };
    match adapter.percent_used() {
        Some(percent) => Tile {
            id: TileId::Gpu,
            label: TileId::Gpu.label(),
            value: render_percent(percent),
            fraction: Some(clamp_fraction(percent)),
            note: format!("{} of {} dedicated", render_bytes(used.0), render_bytes(limit.0)),
            missing: None,
        },
        // An integrated GPU owns no memory of its own: there is memory in use
        // and nothing for it to be a percentage of.
        None => Tile {
            id: TileId::Gpu,
            label: TileId::Gpu.label(),
            value: render_bytes(used.0),
            fraction: None,
            note: "shared memory; no dedicated VRAM".to_owned(),
            missing: None,
        },
    }
}

/// `part` as a percentage of `total`. Not [`Bytes::percent_used`]: that one
/// takes the bytes *available* and answers what is used, which is the inverse
/// of what a row's own memory means.
fn share_of(part: Bytes, total: Bytes) -> Option<f32> {
    if total.0 == 0 {
        return None;
    }
    Some(((part.0.min(total.0) as f64 / total.0 as f64) * 100.0) as f32)
}

fn process_row(process: &ProcessSample, memory_total: Option<Bytes>) -> ProcessRow {
    let (memory, share, known) = match process.working_set.value() {
        Some(bytes) => (render_bytes(bytes.0), memory_total.and_then(|total| share_of(*bytes, total)), true),
        None => (NO_VALUE.to_owned(), None, false),
    };
    let name = if process.name.is_empty() { "unknown".to_owned() } else { process.name.clone() };
    let cpu = process.cpu_percent.value().copied();
    ProcessRow { pid: process.pid, name, memory, share, cpu, known }
}

fn volume_row(volume: &VolumeSample) -> VolumeRow {
    let kind = match volume.kind {
        VolumeKind::Fixed => "fixed",
        VolumeKind::Removable => "removable",
        VolumeKind::Network => "network",
        VolumeKind::Optical => "optical",
        VolumeKind::Ram => "ram",
        VolumeKind::Unknown => "unknown",
    };
    let state = volume.percent_used();
    let detail = match (volume.free.value(), volume.total.value()) {
        (Some(free), Some(total)) => format!("{} free of {}", render_bytes(free.0), render_bytes(total.0)),
        _ => state.why().map(WhyUnknown::explain).unwrap_or("not measured").to_owned(),
    };
    VolumeRow {
        mount: volume.letter().to_owned(),
        kind,
        used_percent: state.value().copied(),
        detail,
        missing: state.why(),
    }
}

fn summary_line(snapshot: &Snapshot, findings: usize) -> String {
    match findings {
        0 => all_clear_sentence(snapshot),
        1 => "One thing needs attention.".to_owned(),
        n => format!("{n} things need attention."),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{CpuSample, GpuAdapter};

    fn bytes(value: u64) -> MetricState<Bytes> {
        MetricState::Value(Bytes(value))
    }

    fn snapshot(seq: u64) -> Snapshot {
        Snapshot {
            seq,
            taken_at: Timestamp(1_700_000_000_000 + seq as i64 * 1000),
            monotonic_ms: seq * 1000,
            cpu: CpuSample {
                percent: MetricState::Value(50.0),
                per_core: vec![MetricState::Value(20.0), MetricState::Value(80.0)],
            },
            memory: MemorySample {
                total: bytes(16 * 1024 * 1024 * 1024),
                available: bytes(8 * 1024 * 1024 * 1024),
                commit_limit: bytes(20 * 1024 * 1024 * 1024),
                commit_used: bytes(9 * 1024 * 1024 * 1024),
                pages_input_per_second: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            },
            volumes: vec![VolumeSample {
                mount: "C:\\".to_owned(),
                kind: VolumeKind::Fixed,
                total: bytes(500 * 1024 * 1024 * 1024),
                free: bytes(50 * 1024 * 1024 * 1024),
            }],
            disk_io: DiskIoSample {
                read_bytes_per_second: bytes(8 * 1024 * 1024),
                write_bytes_per_second: bytes(4 * 1024 * 1024),
                avg_seconds_per_transfer: MetricState::Value(0.004),
            },
            gpu: MetricState::Value(GpuSample {
                adapters: vec![GpuAdapter {
                    instance: "luid_0x00000000_0x0000c4a1_phys_0".to_owned(),
                    dedicated_used: bytes(4 * 1024 * 1024 * 1024),
                    dedicated_limit: bytes(8 * 1024 * 1024 * 1024),
                }],
            }),
            processes: vec![
                ProcessSample {
                    pid: 4242,
                    name: "msedge.exe".to_owned(),
                    working_set: bytes(1024 * 1024 * 1024),
                    cpu_percent: MetricState::Value(12.5),
                    created: MetricState::Value(133_000_000_000_000_000),
                },
                ProcessSample {
                    pid: 88,
                    name: "System".to_owned(),
                    working_set: MetricState::Unknown(WhyUnknown::NeedsElevation),
                    cpu_percent: MetricState::Unknown(WhyUnknown::NotSampledYet),
                    created: MetricState::Unknown(WhyUnknown::NeedsElevation),
                },
            ],
            uptime: MetricState::Value(3 * 3600),
        }
    }

    fn tile(view: &MonitorView, id: TileId) -> &Tile {
        view.tiles.iter().find(|tile| tile.id == id).expect("the tile is always present")
    }

    #[test]
    fn the_overview_shows_four_numbers_with_the_facts_under_them() {
        let view = monitor_view(&snapshot(1), &[snapshot(1)], 0);
        let cpu = tile(&view, TileId::Cpu);
        assert_eq!(cpu.value, "50.0 %");
        assert_eq!(cpu.fraction, Some(0.5));
        assert_eq!(cpu.note, "2 cores, busiest 80.0 %");
        let memory = tile(&view, TileId::Memory);
        assert_eq!(memory.value, "50.0 %");
        assert_eq!(memory.note, "8.0 GB of 16.0 GB in use");
        let disk = tile(&view, TileId::Disk);
        assert_eq!(disk.value, "12.0 MB/s");
        assert_eq!(disk.note, "8.0 MB/s read, 4.0 MB/s written");
        let gpu = tile(&view, TileId::Gpu);
        assert_eq!(gpu.value, "50.0 %");
        assert_eq!(gpu.note, "4.0 GB of 8.0 GB dedicated");
        // A percentage tile gets a ring; throughput has no honest ceiling.
        assert!(disk.fraction.is_none());
        assert!(view.summary.starts_with("Nothing needs attention."), "{}", view.summary);
        assert!(view.summary.contains("measurements are current"), "{}", view.summary);
    }

    #[test]
    fn an_unreadable_tile_says_why_and_never_says_zero() {
        let mut broken = snapshot(2);
        broken.cpu.percent = MetricState::Unknown(WhyUnknown::NotSampledYet);
        broken.memory.available = MetricState::Unknown(WhyUnknown::CollectorFailed);
        broken.disk_io = DiskIoSample::unavailable(WhyUnknown::NotOnThisWindowsVersion);
        broken.gpu = MetricState::Unsupported(WhyUnknown::NotOnThisWindowsVersion);
        let view = monitor_view(&broken, &[broken.clone()], 0);

        for (id, why) in [
            (TileId::Cpu, WhyUnknown::NotSampledYet),
            (TileId::Memory, WhyUnknown::CollectorFailed),
            (TileId::Disk, WhyUnknown::NotOnThisWindowsVersion),
            (TileId::Gpu, WhyUnknown::NotOnThisWindowsVersion),
        ] {
            let tile = tile(&view, id);
            assert_eq!(tile.value, NO_VALUE, "{}", id.id());
            assert_eq!(tile.fraction, None, "{}", id.id());
            assert_eq!(tile.missing, Some(why), "{}", id.id());
            assert_eq!(tile.note, why.explain(), "{}", id.id());
        }
        // The page still has lamps to show; they are just honest ones.
        assert_eq!(view.cpu.gaps(), 1);
        assert_eq!(view.memory.gaps(), 1);
    }

    #[test]
    fn an_integrated_gpu_reports_its_memory_not_a_percentage_of_nothing() {
        let mut integrated = snapshot(3);
        integrated.gpu = MetricState::Value(GpuSample {
            adapters: vec![GpuAdapter {
                instance: "luid_0x00000000_0x0000a1b2_phys_0".to_owned(),
                dedicated_used: bytes(512 * 1024 * 1024),
                dedicated_limit: bytes(0),
            }],
        });
        let view = monitor_view(&integrated, &[integrated.clone()], 0);
        let gpu = tile(&view, TileId::Gpu);
        assert_eq!(gpu.value, "512.0 MB");
        assert_eq!(gpu.fraction, None);
        assert_eq!(gpu.missing, None);
        assert_eq!(gpu.note, "shared memory; no dedicated VRAM");
    }

    #[test]
    fn a_sparkline_keeps_a_missing_sample_as_a_gap() {
        let mut line = Sparkline::new();
        line.push(Some(10.0));
        line.push(None);
        line.push(Some(30.0));
        assert_eq!(line.values(), [Some(10.0), None, Some(30.0)]);
        assert_eq!(line.gaps(), 1);
        assert_eq!(line.normalized(100.0), [Some(0.1), None, Some(0.3)]);
        // Over the ceiling clamps rather than drawing outside the box.
        assert_eq!(line.normalized(20.0), [Some(0.5), None, Some(1.0)]);
        // A ceiling of nothing has nothing to plot.
        assert_eq!(line.normalized(0.0), [None, None, None]);
        assert_eq!(line.latest(), Some(30.0));
    }

    #[test]
    fn a_sparkline_holds_one_minute_and_drops_the_oldest() {
        let mut line = Sparkline::new();
        for value in 0..SPARKLINE_POINTS + 5 {
            line.push(Some(value as f32));
        }
        assert_eq!(line.len(), SPARKLINE_POINTS);
        assert_eq!(line.values().first().copied().flatten(), Some(5.0));
        assert_eq!(line.latest(), Some((SPARKLINE_POINTS + 4) as f32));
    }

    #[test]
    fn the_history_draws_only_what_was_measured() {
        let mut first = snapshot(1);
        first.cpu.percent = MetricState::Value(10.0);
        let mut third = snapshot(3);
        third.cpu.percent = MetricState::Unknown(WhyUnknown::CollectorFailed);
        let view = monitor_view(&third, &[first, snapshot(2), third.clone()], 2);
        assert_eq!(view.cpu.values(), [Some(10.0), Some(50.0), None]);
        assert_eq!(view.cpu.gaps(), 1);
        assert_eq!(view.memory.gaps(), 0);
        assert_eq!(view.summary, "2 things need attention.");
    }

    #[test]
    fn the_process_table_keeps_unreadable_rows_out_of_the_numbers() {
        let view = monitor_view(&snapshot(1), &[snapshot(1)], 1);
        assert_eq!(view.processes.len(), 2);
        let edge = &view.processes[0];
        assert_eq!((edge.pid, edge.name.as_str(), edge.memory.as_str()), (4242, "msedge.exe", "1.0 GB"));
        assert_eq!(edge.share, Some(6.25));
        assert_eq!(edge.cpu, Some(12.5));
        assert!(edge.known);
        // The row is there — it exists on this machine — but its number is not
        // a number, and its share is not 0 %.
        let system = &view.processes[1];
        assert_eq!(system.memory, NO_VALUE);
        assert_eq!(system.share, None);
        assert_eq!(system.cpu, None, "an unmeasured CPU is not 0 %");
        assert!(!system.known);
        assert_eq!(view.summary, "One thing needs attention.");
    }

    #[test]
    fn the_wire_format_keeps_unknown_out_of_the_numbers() {
        let mut broken = snapshot(1);
        broken.cpu.percent = MetricState::Unknown(WhyUnknown::NotSampledYet);
        let json = serde_json::to_value(monitor_view(&broken, &[broken.clone()], 0)).expect("serializes");
        let cpu = &json["tiles"][0];
        assert_eq!(cpu["id"], "cpu");
        assert_eq!(cpu["value"], NO_VALUE);
        assert_eq!(cpu["fraction"], serde_json::Value::Null);
        assert_eq!(cpu["note"], WhyUnknown::NotSampledYet.explain());
        assert_eq!(cpu["missing"], "not_sampled_yet");
        // The same rule holds for the process table: the row is on the wire, its
        // rate is null.
        assert_eq!(json["processes"][1]["cpu"], serde_json::Value::Null);
        assert_eq!(json["processes"][0]["cpu"], 12.5);
        // Gaps survive the trip: null stays null rather than becoming zero.
        assert_eq!(json["cpu"], serde_json::json!([serde_json::Value::Null]));
        assert_eq!(json["tiles"][1]["value"], "50.0 %");
    }

    #[test]
    fn the_detail_view_gets_the_fields_it_reads() {
        let mut partly = snapshot(1);
        partly.cpu.per_core =
            vec![MetricState::Value(20.0), MetricState::Unknown(WhyUnknown::CollectorFailed)];
        let json =
            serde_json::to_value(monitor_view(&partly, &[partly.clone()], 0)).expect("serializes");
        // A core that was not measured arrives as null, not as zero: the bar is
        // drawn empty either way, but only one of them is a lie.
        assert_eq!(json["cores"][0]["percent"], 20.0);
        assert_eq!(json["cores"][1]["percent"], serde_json::Value::Null);
        // A volume carries its share for the bar and its words for the row.
        assert_eq!(json["volumes"][0]["usedPercent"], 90.0);
        assert_eq!(json["volumes"][0]["kind"], "fixed");
        // A process whose memory could not be read is still a row, and says so.
        assert_eq!(json["processes"][1]["known"], false);
        assert_eq!(json["processes"][1]["memory"], NO_VALUE);
    }

    #[test]
    fn volumes_are_listed_with_their_share_and_kind() {
        let mut unknown = snapshot(1);
        unknown.volumes[0].free = MetricState::Unsupported(WhyUnknown::NotOnThisWindowsVersion);
        let view = monitor_view(&unknown, &[unknown.clone()], 0);
        let row = &view.volumes[0];
        assert_eq!((row.mount.as_str(), row.kind), ("C:", "fixed"));
        assert_eq!(row.used_percent, Some(90.0));
        assert_eq!(row.detail, "50.0 GB free of 500.0 GB");
        assert_eq!(row.missing, None);

        let broken = monitor_view(&snapshot(1), &[snapshot(1)], 0);
        let row = &broken.volumes[0];
        assert_eq!(row.missing, None);
        assert_eq!(view.cores.len(), 2);
    }
}
