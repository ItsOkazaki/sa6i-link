// SPDX-License-Identifier: MPL-2.0
//! The words a measurement report is made of.
//!
//! Both front-ends print the same report — the standalone
//! `sa6i-intel-snapshot` binary and `sa6i-link intel snapshot` — so the sentences
//! live here, once. A metric that could not be read says why in the same way in
//! both places, which is the only way the two can be trusted to agree.
//!
//! The lines are `Vec<String>` rather than printed: the caller owns the stream
//! (`--json` must stay pure JSON on stdout) and the tests can check the wording
//! without a terminal.

use std::time::Duration;

use sa6i_link_intel::{
    Bytes, DiskIoSample, Finding, GpuSample, MetricState, ProcessSample, Snapshot, WindowSummary,
    all_clear_sentence, human_duration, render_bytes, render_percent,
};

/// A per-core line that never invents a core count.
///
/// It says how many were *measured*, because on a machine with more than one
/// processor group Windows answers per group and the list is short.
fn describe_cores(cores: &[MetricState<f32>]) -> String {
    let known: Vec<f32> = cores.iter().filter_map(|state| state.value().copied()).collect();
    if known.is_empty() {
        return format!("{} core(s) seen, none measured yet", cores.len());
    }
    let busy = known.iter().filter(|percent| **percent >= 50.0).count();
    let busiest = known.iter().copied().fold(0.0_f32, f32::max);
    format!("{} measured, {busy} above half, busiest {}", known.len(), render_percent(busiest))
}

/// `"read 12.4 MB/s, write 840 kB/s"`, or why there is no number.
fn describe_disk_io(io: &DiskIoSample) -> String {
    let rate = |state: MetricState<Bytes>| match state {
        MetricState::Value(bytes) => format!("{}/s", render_bytes(bytes.0)),
        MetricState::Unknown(reason) | MetricState::Unsupported(reason) => {
            format!("— ({})", reason.explain())
        }
    };
    format!("read {}, write {}", rate(io.read_bytes_per_second), rate(io.write_bytes_per_second))
}

/// The adapter with the most dedicated memory, or why there is nothing to say.
fn describe_gpu(gpu: &MetricState<GpuSample>) -> String {
    let sample = match gpu {
        MetricState::Value(sample) => sample,
        MetricState::Unknown(reason) | MetricState::Unsupported(reason) => {
            return format!("— ({})", reason.explain());
        }
    };
    let Some(adapter) = sample.heaviest() else {
        return "— (no adapters reported)".to_owned();
    };
    match (adapter.dedicated_used.value(), adapter.dedicated_limit.value()) {
        (Some(used), Some(limit)) => match adapter.percent_used() {
            Some(percent) => {
                format!("{} of {} ({})", render_bytes(used.0), render_bytes(limit.0), render_percent(percent))
            }
            // An integrated GPU: memory in use, nothing of its own to be a
            // percentage of.
            None => format!("{} used, no dedicated memory", render_bytes(used.0)),
        },
        _ => "— (the counters answered without a value)".to_owned(),
    }
}

/// `"msedge.exe 1.2 GB 12.5 %, chrome.exe 900 MB 0.4 %"` for the busiest few — the
/// rate is left out for a process that has only been seen once — or `"none measured"`.
fn describe_processes(processes: &[ProcessSample]) -> String {
    let described: Vec<String> = processes
        .iter()
        .take(3)
        .map(|process| {
            let memory = match process.working_set {
                MetricState::Value(bytes) => render_bytes(bytes.0),
                _ => "(size not readable)".to_owned(),
            };
            match process.cpu_percent {
                MetricState::Value(percent) => {
                    format!("{} {} {}", process.name, memory, render_percent(percent))
                }
                _ => format!("{} {}", process.name, memory),
            }
        })
        .collect();
    if described.is_empty() {
        return "none measured".to_owned();
    }
    format!("{} busiest: {}", processes.len(), described.join(", "))
}

/// `"— (requires administrator rights)"`, or a dash when nothing is wrong.
fn describe<T>(state: &MetricState<T>) -> String {
    match state.why() {
        Some(reason) => format!("— ({})", reason.explain()),
        None => "—".to_owned(),
    }
}

/// Everything measured in one snapshot, as report lines.
///
/// `average` inserts the window's mean where a person reads it: after the
/// instantaneous numbers and before the machine's uptime.
pub fn report_lines(snapshot: &Snapshot, average: Option<&WindowSummary>) -> Vec<String> {
    let mut lines = Vec::new();
    match snapshot.cpu.percent {
        MetricState::Value(percent) => lines.push(format!("  cpu        {}", render_percent(percent))),
        other => lines.push(format!("  cpu        {}", describe(&other))),
    }
    if !snapshot.cpu.per_core.is_empty() {
        lines.push(format!("  cores      {}", describe_cores(&snapshot.cpu.per_core)));
    }
    lines.push(format!("  disk io    {}", describe_disk_io(&snapshot.disk_io)));
    lines.push(format!("  gpu        {}", describe_gpu(&snapshot.gpu)));
    if !snapshot.processes.is_empty() {
        lines.push(format!("  processes  {}", describe_processes(&snapshot.processes)));
    }
    match (snapshot.memory.percent_used(), snapshot.memory.total) {
        (MetricState::Value(percent), MetricState::Value(total)) => {
            lines.push(format!("  memory     {} used of {}", render_percent(percent), render_bytes(total.0)))
        }
        (state, _) => lines.push(format!("  memory     {}", describe(&state))),
    }
    for volume in &snapshot.volumes {
        match (volume.percent_used(), volume.free, volume.total) {
            (MetricState::Value(percent), MetricState::Value(free), MetricState::Value(total)) => {
                lines.push(format!(
                    "  {:<10} {} used — {} free of {}",
                    volume.letter(),
                    render_percent(percent),
                    render_bytes(free.0),
                    render_bytes(total.0)
                ));
            }
            _ => lines.push(format!("  {:<10} — (could not be read)", volume.letter())),
        }
    }
    if let Some(average) = average {
        lines.push(format!("  average    {}", average.line()));
    }
    match snapshot.uptime {
        MetricState::Value(seconds) => {
            lines.push(format!("  uptime     {}", human_duration(seconds.saturating_mul(1000))));
        }
        other => lines.push(format!("  uptime     {}", describe(&other))),
    }
    lines
}

/// What the rules made of the snapshot: an all-clear sentence, or each finding
/// with its explanation and the measurements behind it.
pub fn findings_lines(snapshot: &Snapshot, findings: &[Finding], samples: u32) -> Vec<String> {
    if findings.is_empty() {
        let mut lines = vec![format!("  {}", all_clear_sentence(snapshot))];
        if samples == 1 {
            lines.push(
                "  (One sample cannot confirm anything that needs a window: \
                 try --samples 700 for a ten-minute view.)"
                    .to_owned(),
            );
        }
        return lines;
    }
    let mut lines = Vec::new();
    for finding in findings {
        lines.push(format!("  [{}] {}", finding.severity.label(), finding.title));
        lines.push(format!("        {}", finding.explain));
        for evidence in &finding.evidence {
            lines.push(format!("        · {}", evidence.sentence()));
        }
    }
    lines
}

/// CPU time this process has used (kernel + user), or `None` where it cannot be
/// read.
///
/// Windows counts in 100 ns units and asks for four `FILETIME`s of which only
/// the last two are used. The pseudo-handle from `GetCurrentProcess` needs no
/// closing.
#[cfg(windows)]
#[allow(unsafe_code)]
pub fn process_cpu_time() -> Option<Duration> {
    use windows::Win32::Foundation::FILETIME;
    use windows::Win32::System::Threading::{GetCurrentProcess, GetProcessTimes};
    let mut creation = FILETIME::default();
    let mut exit = FILETIME::default();
    let mut kernel = FILETIME::default();
    let mut user = FILETIME::default();
    // SAFETY: the handle is a pseudo-handle that is not closed, and all four
    // out-pointers point at locals that outlive the call.
    unsafe { GetProcessTimes(GetCurrentProcess(), &mut creation, &mut exit, &mut kernel, &mut user) }.ok()?;
    let ticks = |time: FILETIME| (u64::from(time.dwHighDateTime) << 32) | u64::from(time.dwLowDateTime);
    Some(Duration::from_nanos(ticks(kernel).saturating_add(ticks(user)).saturating_mul(100)))
}

/// No way to read it off Windows, and a guess would be worse than a blank.
#[cfg(not(windows))]
pub fn process_cpu_time() -> Option<Duration> {
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use sa6i_link_intel::{CpuSample, MemorySample, Timestamp, VolumeKind, VolumeSample, WhyUnknown};

    fn bytes(value: u64) -> MetricState<Bytes> {
        MetricState::Value(Bytes(value))
    }

    fn snapshot() -> Snapshot {
        Snapshot {
            seq: 1,
            taken_at: Timestamp(1_700_000_000_000),
            monotonic_ms: 0,
            cpu: CpuSample {
                percent: MetricState::Value(12.5),
                per_core: vec![MetricState::Value(10.0), MetricState::Unknown(WhyUnknown::CollectorFailed)],
            },
            memory: MemorySample {
                total: bytes(16 * 1024 * 1024 * 1024),
                available: bytes(8 * 1024 * 1024 * 1024),
                commit_limit: bytes(20 * 1024 * 1024 * 1024),
                commit_used: bytes(9 * 1024 * 1024 * 1024),
                pages_input_per_second: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            },
            volumes: vec![
                VolumeSample {
                    mount: "C:\\".to_owned(),
                    kind: VolumeKind::Fixed,
                    total: bytes(500 * 1024 * 1024 * 1024),
                    free: bytes(50 * 1024 * 1024 * 1024),
                },
                VolumeSample {
                    mount: "D:\\".to_owned(),
                    kind: VolumeKind::Fixed,
                    total: MetricState::Unknown(WhyUnknown::CollectorFailed),
                    free: MetricState::Unknown(WhyUnknown::CollectorFailed),
                },
            ],
            disk_io: DiskIoSample::unavailable(WhyUnknown::NotOnThisWindowsVersion),
            gpu: MetricState::Unsupported(WhyUnknown::NotOnThisWindowsVersion),
            processes: Vec::new(),
            uptime: MetricState::Value(3 * 3600),
        }
    }

    #[test]
    fn the_lines_say_what_was_measured_and_what_was_not() {
        let lines = report_lines(&snapshot(), None);
        assert_eq!(lines[0], "  cpu        12.5 %");
        // Two cores seen, one measured: the line says the number it has.
        assert_eq!(lines[1], "  cores      1 measured, 0 above half, busiest 10.0 %");
        assert_eq!(
            lines[2],
            "  disk io    read — (not available on this version of Windows), \
             write — (not available on this version of Windows)"
        );
        assert_eq!(lines[3], "  gpu        — (not available on this version of Windows)");
        // No processes were collected, so there is no line pretending otherwise.
        assert!(lines.iter().all(|line| !line.starts_with("  processes")));
        assert_eq!(lines[4], "  memory     50.0 % used of 16.0 GB");
        assert_eq!(lines[5], "  C:         90.0 % used — 50.0 GB free of 500.0 GB");
        assert_eq!(lines[6], "  D:         — (could not be read)");
        assert_eq!(lines[7], "  uptime     3 hours");
    }

    #[test]
    fn the_average_lands_before_the_uptime() {
        let snapshot = snapshot();
        let average = WindowSummary::of(std::slice::from_ref(&snapshot));
        let lines = report_lines(&snapshot, Some(&average));
        let average_at = lines.iter().position(|line| line.starts_with("  average")).expect("an average");
        let uptime_at = lines.iter().position(|line| line.starts_with("  uptime")).expect("an uptime");
        assert!(average_at < uptime_at);
        assert_eq!(
            lines[average_at],
            "  average    cpu 12.5 % (1 of 1 samples) · memory 50.0 % (1 of 1 samples) · over 1 second"
        );
    }

    #[test]
    fn one_sample_says_what_it_cannot_confirm() {
        let lines = findings_lines(&snapshot(), &[], 1);
        assert!(lines[0].starts_with("  Nothing needs attention."));
        assert!(lines[1].contains("One sample cannot confirm"));
        // With a window behind it, the caveat is gone.
        assert_eq!(findings_lines(&snapshot(), &[], 700).len(), 1);
    }
}
