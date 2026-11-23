// SPDX-License-Identifier: MPL-2.0
//! `sa6i-intel-snapshot`: measure this machine and print what Sa6i would say.
//!
//! The headless proof that the engine works without a window, a phone or a
//! model — the same code the Monitor page will call.
//!
//! ```text
//! cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot
//! cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- --samples 700
//! cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- --json
//!
//! # M1's two checks that need a real machine:
//! # 60 samples averaged, to hold next to Task Manager's Performance tab.
//! cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- \
//!     --samples 60 --interval-ms 1000 --average
//! # The plan's thirty minutes at 1 Hz, with a verdict and exit code 3 on a miss.
//! cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- \
//!     --samples 1800 --interval-ms 1000 --budget
//! ```

use std::{
    path::Path,
    thread::sleep,
    time::{Duration, Instant},
};

use sa6i_link_intel::{
    History, MetricState, ProcessSample, SampleStore, Timestamp, WindowSummary,
    all_clear_sentence, evaluate, human_duration, render_bytes, render_percent,
};
use sa6i_link_intel_win::WindowsCollector;

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
    format!(
        "{} measured, {busy} above half, busiest {}",
        known.len(),
        render_percent(busiest)
    )
}

/// `"read 12.4 MB/s, write 840 kB/s"`, or why there is no number.
fn describe_disk_io(io: &sa6i_link_intel::DiskIoSample) -> String {
    let rate = |state: MetricState<sa6i_link_intel::Bytes>| match state {
        MetricState::Value(bytes) => format!("{}/s", render_bytes(bytes.0)),
        MetricState::Unknown(reason) | MetricState::Unsupported(reason) => {
            format!("— ({})", reason.explain())
        }
    };
    format!(
        "read {}, write {}",
        rate(io.read_bytes_per_second),
        rate(io.write_bytes_per_second)
    )
}

/// The adapter with the most dedicated memory, or why there is nothing to say.
fn describe_gpu(gpu: &MetricState<sa6i_link_intel::GpuSample>) -> String {
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
            Some(percent) => format!(
                "{} of {} ({})",
                render_bytes(used.0),
                render_bytes(limit.0),
                render_percent(percent)
            ),
            // An integrated GPU: memory in use, nothing of its own to be a
            // percentage of.
            None => format!("{} used, no dedicated memory", render_bytes(used.0)),
        },
        _ => "— (the counters answered without a value)".to_owned(),
    }
}

/// `"msedge.exe 1.2 GB, chrome.exe 900 MB"` for the heaviest few, or why not.
fn describe_processes(processes: &[ProcessSample]) -> String {
    let described: Vec<String> = processes
        .iter()
        .take(3)
        .map(|process| match process.working_set {
            MetricState::Value(bytes) => format!("{} {}", process.name, render_bytes(bytes.0)),
            _ => format!("{} (size not readable)", process.name),
        })
        .collect();
    if described.is_empty() {
        return "none measured".to_owned();
    }
    format!("{} heaviest: {}", processes.len(), described.join(", "))
}

/// `"— (requires administrator rights)"`, or the value if there is one.
fn describe<T>(state: &MetricState<T>) -> String {
    match state.why() {
        Some(reason) => format!("— ({})", reason.explain()),
        None => "—".to_owned(),
    }
}

/// A sample may spend at most this share of the interval collecting.
const SAMPLE_SHARE: f64 = 0.25;
/// The whole process may use at most this share of one core.
const CPU_SHARE: f64 = 0.01;
/// How far off the requested rate still counts as holding it.
const RATE_TOLERANCE: f64 = 0.05;

/// What one run cost: the wall clock, each sample's own time, and this
/// process's CPU time where the platform will say.
struct Cost {
    elapsed: Duration,
    per_sample: Vec<Duration>,
    cpu: Option<Duration>,
}

/// CPU time this process has used (kernel + user), or `None` where it cannot be
/// read.
///
/// Windows counts in 100 ns units and asks for four `FILETIME`s of which only
/// the last two are used. The pseudo-handle from `GetCurrentProcess` needs no
/// closing.
#[cfg(windows)]
#[allow(unsafe_code)]
fn process_cpu_time() -> Option<Duration> {
    use windows::Win32::Foundation::FILETIME;
    use windows::Win32::System::Threading::{GetCurrentProcess, GetProcessTimes};
    let mut creation = FILETIME::default();
    let mut exit = FILETIME::default();
    let mut kernel = FILETIME::default();
    let mut user = FILETIME::default();
    // SAFETY: the handle is a pseudo-handle that is not closed, and all four
    // out-pointers point at locals that outlive the call.
    unsafe { GetProcessTimes(GetCurrentProcess(), &mut creation, &mut exit, &mut kernel, &mut user) }
        .ok()?;
    let ticks =
        |time: FILETIME| (u64::from(time.dwHighDateTime) << 32) | u64::from(time.dwLowDateTime);
    Some(Duration::from_nanos(
        ticks(kernel).saturating_add(ticks(user)).saturating_mul(100),
    ))
}

/// No way to read it off Windows, and a guess would be worse than a blank.
#[cfg(not(windows))]
fn process_cpu_time() -> Option<Duration> {
    None
}

/// Prints what the run cost and whether it held. Returns false on a miss.
///
/// The three things "1 Hz under budget" means, spelled out: the rate held, no
/// sample took longer than its interval, and the process stayed inside its share
/// of a core. CPU is skipped rather than failed where it could not be measured —
/// an unmeasured cost is not a cheap one.
fn print_budget(samples: u32, interval: Duration, cost: &Cost) -> bool {
    let count = cost.per_sample.len().max(1);
    let seconds = |d: Duration| d.as_secs_f64();
    let mean = cost.per_sample.iter().copied().map(seconds).sum::<f64>() / count as f64;
    let worst = cost.per_sample.iter().copied().map(seconds).fold(0.0, f64::max);
    let achieved = if samples > 1 { f64::from(samples - 1) / seconds(cost.elapsed) } else { 0.0 };
    let target = 1.0 / seconds(interval);
    let share = cost.cpu.map(|cpu| seconds(cpu) / seconds(cost.elapsed));

    let rate_ok = samples < 2 || (achieved / target - 1.0).abs() <= RATE_TOLERANCE;
    let sample_ok = mean <= seconds(interval) * SAMPLE_SHARE && worst <= seconds(interval);
    let cpu_ok = share.map_or(true, |share| share <= CPU_SHARE);

    let mark = |ok: bool| if ok { "ok" } else { "OVER" };
    println!();
    println!("  budget");
    println!(
        "    rate       {achieved:.2} Hz of {target:.2} Hz over {} — {}",
        human_duration(u64::try_from(cost.elapsed.as_millis()).unwrap_or(u64::MAX)),
        mark(rate_ok)
    );
    println!(
        "    collection mean {:.1} ms, worst {:.1} ms, ceiling {:.0} ms — {}",
        mean * 1000.0,
        worst * 1000.0,
        seconds(interval) * 1000.0,
        mark(sample_ok)
    );
    match share {
        Some(share) => println!(
            "    cpu        {:.2} % of one core, ceiling {:.0} % — {}",
            share * 100.0,
            CPU_SHARE * 100.0,
            mark(cpu_ok)
        ),
        None => println!("    cpu        — (not measurable on this platform)"),
    }
    let passed = rate_ok && sample_ok && cpu_ok;
    println!("    verdict    {}", if passed { "PASS" } else { "MISS" });
    passed
}

fn main() {
    let mut samples: u32 = 1;
    let mut interval_ms: u64 = 1000;
    let mut json = false;
    let mut show_findings = true;
    let mut history_path: Option<String> = None;
    let mut average = false;
    let mut budget = false;

    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--samples" => {
                samples = args.next().and_then(|v| v.parse().ok()).unwrap_or(1);
            }
            "--interval-ms" => {
                interval_ms = args.next().and_then(|v| v.parse().ok()).unwrap_or(1000);
            }
            "--json" => json = true,
            "--no-findings" => show_findings = false,
            "--history" => history_path = args.next(),
            "--average" => average = true,
            "--budget" => budget = true,
            "--help" | "-h" => {
                println!("usage: sa6i-intel-snapshot [--samples N] [--interval-ms MS]");
                println!("       [--json] [--no-findings] [--history PATH] [--average] [--budget]");
                println!();
                println!("--average  print the window's mean cpu and memory, which is what");
                println!("           Task Manager's Performance tab shows; use --samples 60");
                println!("           --interval-ms 1000 to compare per the exit criteria");
                println!("--budget   print the cost of sampling and whether it held: use");
                println!("           --samples 1800 --interval-ms 1000 for the thirty-minute");
                println!("           check. Exits 3 on a miss.");
                return;
            }
            other => {
                eprintln!("unknown argument: {other}");
                std::process::exit(2);
            }
        }
    }

    let samples = samples.max(1);
    let interval = Duration::from_millis(interval_ms.max(1));

    let mut collector = WindowsCollector::new();
    let mut store = SampleStore::default();
    let mut cost = Cost { elapsed: Duration::ZERO, per_sample: Vec::new(), cpu: None };
    let cpu_before = budget.then(process_cpu_time).flatten();
    let started = Instant::now();
    for index in 0..samples {
        if index > 0 {
            sleep(interval);
        }
        let begin = Instant::now();
        let snapshot = collector.next_snapshot();
        if budget {
            cost.per_sample.push(begin.elapsed());
        }
        store.push(snapshot);
    }
    cost.elapsed = started.elapsed();
    cost.cpu = match (cpu_before, budget.then(process_cpu_time).flatten()) {
        (Some(before), Some(after)) => after.checked_sub(before),
        _ => None,
    };

    let snapshot = store.latest().expect("at least one sample");
    let findings = if show_findings { evaluate(snapshot, &store) } else { Vec::new() };

    // Durable history is opt-in: no file is ever written unless asked for, and a
    // failure to write it is reported on stderr so `--json` stays pure JSON.
    if let Some(path) = history_path {
        match History::open(Path::new(&path)) {
            Ok(mut history) => {
                let mut stored = 0usize;
                for sample in store.samples() {
                    if matches!(history.record(sample), Ok(true)) {
                        stored += 1;
                    }
                }
                let pruned = history.prune(Timestamp::now()).unwrap_or(0);
                if let Err(error) = history.record_findings(&findings) {
                    eprintln!("history: findings not stored: {error}");
                }
                match history.counts() {
                    Ok((held_samples, held_findings)) => eprintln!(
                        "history: {stored} of {samples} sample(s) stored, {pruned} pruned — \
                         {held_samples} sample(s), {held_findings} finding(s) now held in {path}"
                    ),
                    Err(error) => eprintln!("history: {error}"),
                }
            }
            Err(error) => {
                eprintln!("history: can't open {path}: {error}");
                std::process::exit(1);
            }
        }
    }

    let summary = average.then(|| WindowSummary::of(&store.samples().cloned().collect::<Vec<_>>()));

    if json {
        let mut payload = serde_json::json!({ "snapshot": snapshot, "findings": findings });
        if let Some(summary) = &summary {
            payload["summary"] = serde_json::json!(summary);
        }
        match serde_json::to_string_pretty(&payload) {
            Ok(text) => println!("{text}"),
            Err(error) => {
                eprintln!("can't serialize the snapshot: {error}");
                std::process::exit(1);
            }
        }
        return;
    }

    println!("Sa6i — this machine, measured");
    println!(
        "  sample {} of {} (history covers {} s)",
        snapshot.seq,
        samples,
        store.span_ms() / 1000
    );
    println!();

    match snapshot.cpu.percent {
        MetricState::Value(percent) => println!("  cpu        {}", render_percent(percent)),
        other => println!("  cpu        {}", describe(&other)),
    }
    if !snapshot.cpu.per_core.is_empty() {
        println!("  cores      {}", describe_cores(&snapshot.cpu.per_core));
    }
    println!("  disk io    {}", describe_disk_io(&snapshot.disk_io));
    println!("  gpu        {}", describe_gpu(&snapshot.gpu));
    if !snapshot.processes.is_empty() {
        println!("  processes  {}", describe_processes(&snapshot.processes));
    }

    match (snapshot.memory.percent_used(), snapshot.memory.total) {
        (MetricState::Value(percent), MetricState::Value(total)) => println!(
            "  memory     {} used of {}",
            render_percent(percent),
            render_bytes(total.0)
        ),
        (state, _) => println!("  memory     {}", describe(&state)),
    }

    for volume in &snapshot.volumes {
        match (volume.percent_used(), volume.free, volume.total) {
            (MetricState::Value(percent), MetricState::Value(free), MetricState::Value(total)) => {
                println!(
                    "  {:<10} {} used — {} free of {}",
                    volume.letter(),
                    render_percent(percent),
                    render_bytes(free.0),
                    render_bytes(total.0)
                );
            }
            _ => println!("  {:<10} — (could not be read)", volume.letter()),
        }
    }

    if let Some(summary) = &summary {
        println!("  average    {}", summary.line());
    }

    match snapshot.uptime {
        MetricState::Value(seconds) => {
            println!("  uptime     {}", human_duration(seconds.saturating_mul(1000)));
        }
        other => println!("  uptime     {}", describe(&other)),
    }

    println!();
    if findings.is_empty() {
        println!("  {}", all_clear_sentence(snapshot));
        if samples == 1 {
            println!(
                "  (One sample cannot confirm anything that needs a window: \
                 try --samples 700 for a ten-minute view.)"
            );
        }
    } else {
        for finding in &findings {
            println!("  [{}] {}", finding.severity.label(), finding.title);
            println!("        {}", finding.explain);
            for evidence in &finding.evidence {
                println!("        · {}", evidence.sentence());
            }
        }
    }

    // A miss is a result, not a crash: the numbers are printed either way and
    // the exit code is what a script (or CI, or the next person) reads.
    if budget && !print_budget(samples, interval, &cost) {
        std::process::exit(3);
    }
}
