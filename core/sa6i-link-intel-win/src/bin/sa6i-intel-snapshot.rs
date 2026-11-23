// SPDX-License-Identifier: MPL-2.0
//! `sa6i-intel-snapshot`: measure this machine and print what Sa6i would say.
//!
//! The headless proof that the engine works without a window, a phone or a
//! model — the same code the Monitor page calls. The words come from
//! [`sa6i_link_intel_win::report`], which `sa6i-link intel snapshot` prints too.
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

use std::{path::Path, time::Duration};

use sa6i_link_intel::{History, Timestamp, Verdict, WindowSummary, evaluate};
use sa6i_link_intel_win::{report, sample_window};

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
    let interval_ms = interval_ms.max(1);
    let interval = Duration::from_millis(interval_ms);

    let (store, cost) = sample_window(samples, interval, budget);

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

    let summary =
        average.then(|| WindowSummary::of(&store.samples().cloned().collect::<Vec<_>>()));

    // The verdict is computed before the output choice, so `--budget` means the
    // same thing in both formats and `--json --budget` is not a silent no-op.
    let verdict = budget.then(|| Verdict::judge(samples, interval_ms, &cost));

    if json {
        let mut payload = serde_json::json!({ "snapshot": snapshot, "findings": findings });
        if let Some(summary) = &summary {
            payload["summary"] = serde_json::json!(summary);
        }
        if let Some(verdict) = &verdict {
            payload["budget"] = serde_json::json!(verdict);
        }
        match serde_json::to_string_pretty(&payload) {
            Ok(text) => println!("{text}"),
            Err(error) => {
                eprintln!("can't serialize the snapshot: {error}");
                std::process::exit(1);
            }
        }
        match verdict {
            Some(verdict) if !verdict.passed() => std::process::exit(3),
            _ => return,
        }
    }

    println!("Sa6i — this machine, measured");
    println!(
        "  sample {} of {} (history covers {} s)",
        snapshot.seq,
        samples,
        store.span_ms() / 1000
    );
    println!();
    for line in report::report_lines(snapshot, summary.as_ref()) {
        println!("{line}");
    }
    println!();
    for line in report::findings_lines(snapshot, &findings, samples) {
        println!("{line}");
    }

    // A miss is a result, not a crash: the numbers are printed either way and
    // the exit code is what a script (or CI, or the next person) reads.
    if let Some(verdict) = verdict {
        for line in verdict.render() {
            println!("  {line}");
        }
        if !verdict.passed() {
            std::process::exit(3);
        }
    }
}
