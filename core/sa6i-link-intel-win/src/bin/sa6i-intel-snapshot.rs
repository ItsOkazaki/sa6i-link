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
//! ```

use std::{path::Path, thread::sleep, time::Duration};

use sa6i_link_intel::{
    History, MetricState, SampleStore, Timestamp, all_clear_sentence, evaluate, human_duration,
    render_bytes, render_percent,
};
use sa6i_link_intel_win::WindowsCollector;

/// `"— (requires administrator rights)"`, or the value if there is one.
fn describe<T>(state: &MetricState<T>) -> String {
    match state.why() {
        Some(reason) => format!("— ({})", reason.explain()),
        None => "—".to_owned(),
    }
}

fn main() {
    let mut samples: u32 = 1;
    let mut interval_ms: u64 = 1000;
    let mut json = false;
    let mut show_findings = true;
    let mut history_path: Option<String> = None;

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
            "--help" | "-h" => {
                println!(
                    "usage: sa6i-intel-snapshot [--samples N] [--interval-ms MS] \
                     [--json] [--no-findings] [--history PATH]"
                );
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
    for index in 0..samples {
        if index > 0 {
            sleep(interval);
        }
        store.push(collector.next_snapshot());
    }

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

    if json {
        let payload = serde_json::json!({ "snapshot": snapshot, "findings": findings });
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
}
