// SPDX-License-Identifier: MPL-2.0
//! What sampling cost, and whether it held — the arithmetic behind `--budget`.
//!
//! M1's plan asks for "1 Hz for 30 min under budget" without saying what the
//! budget is. This is the definition: a sample may spend at most a quarter of
//! its interval collecting, no single sample may overrun the interval, the
//! achieved rate must stay within 5 % of the requested one, and the whole
//! process must use under 1 % of one core.
//!
//! The verdict is here, in the platform-free crate, so it can be tested with
//! invented timings instead of a stopwatch: a run that was too slow, too
//! irregular, or too expensive has to be able to fail, or the check is theatre.

use serde::Serialize;

/// The most of its interval a single sample may spend collecting.
pub const SAMPLE_SHARE: f64 = 0.25;
/// The most of one core the whole process may use, averaged over the run.
pub const CPU_SHARE: f64 = 0.01;
/// How far off the requested rate still counts as holding it.
pub const RATE_TOLERANCE: f64 = 0.05;

/// What one run cost.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct Cost {
    /// Wall-clock time for the whole run.
    pub elapsed_ms: f64,
    /// How long each sample spent inside the collector.
    pub per_sample_ms: Vec<f64>,
    /// This process's CPU time over the run, where the platform says.
    pub cpu_ms: Option<f64>,
}

/// Whether the run held, in the three ways that matter.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Verdict {
    /// Samples the run asked for.
    pub samples: u32,
    /// Samples per second actually achieved.
    pub rate_hz: f64,
    /// Samples per second asked for.
    pub target_hz: f64,
    pub rate_ok: bool,
    /// Mean time a sample spent collecting.
    pub mean_ms: f64,
    /// The slowest sample.
    pub worst_ms: f64,
    /// How long a sample has before it is late: one interval.
    pub ceiling_ms: f64,
    pub sample_ok: bool,
    /// Share of one core the process used, where it could be measured.
    pub cpu_share: Option<f64>,
    /// `false` only when a measurement exists and is too high: an unmeasured
    /// cost is not a cheap one, but it is not a failing one either.
    pub cpu_ok: bool,
}

impl Verdict {
    /// Judge a run of `samples` samples at `interval_ms` apart.
    pub fn judge(samples: u32, interval_ms: u64, cost: &Cost) -> Self {
        let interval = interval_ms.max(1) as f64;
        let count = cost.per_sample_ms.len();
        let mean_ms = if count == 0 { 0.0 } else { cost.per_sample_ms.iter().sum::<f64>() / count as f64 };
        let worst_ms = cost.per_sample_ms.iter().copied().fold(0.0, f64::max);
        // One interval per gap: the first sample has nothing to wait for.
        let rate_hz = if samples > 1 && cost.elapsed_ms > 0.0 {
            f64::from(samples - 1) / (cost.elapsed_ms / 1000.0)
        } else {
            0.0
        };
        let target_hz = 1000.0 / interval;
        let cpu_share = cost
            .cpu_ms
            .filter(|_| cost.elapsed_ms > 0.0)
            .map(|cpu| cpu / cost.elapsed_ms);
        Self {
            samples,
            rate_hz,
            target_hz,
            rate_ok: samples < 2 || (rate_hz / target_hz - 1.0).abs() <= RATE_TOLERANCE,
            mean_ms,
            worst_ms,
            ceiling_ms: interval,
            sample_ok: mean_ms <= interval * SAMPLE_SHARE && worst_ms <= interval,
            cpu_share,
            cpu_ok: cpu_share.is_none_or(|share| share <= CPU_SHARE),
        }
    }

    /// Whether every part held.
    pub fn passed(&self) -> bool {
        self.rate_ok && self.sample_ok && self.cpu_ok
    }

    /// The block `--budget` prints. Three numbers and a verdict, no adjectives.
    pub fn render(&self) -> Vec<String> {
        let mark = |ok: bool| if ok { "ok" } else { "OVER" };
        let cpu = match self.cpu_share {
            Some(share) => format!(
                "cpu        {:.2} % of one core, ceiling {:.0} % — {}",
                share * 100.0,
                CPU_SHARE * 100.0,
                mark(self.cpu_ok)
            ),
            None => "cpu        — (not measurable on this platform)".to_owned(),
        };
        vec![
            "budget".to_owned(),
            format!(
                "  rate       {:.2} Hz of {:.2} Hz over {} samples — {}",
                self.rate_hz,
                self.target_hz,
                self.samples,
                mark(self.rate_ok)
            ),
            format!(
                "  collection mean {:.1} ms, worst {:.1} ms, ceiling {:.0} ms — {}",
                self.mean_ms,
                self.worst_ms,
                self.ceiling_ms,
                mark(self.sample_ok)
            ),
            format!("  {cpu}"),
            format!("  verdict    {}", if self.passed() { "PASS" } else { "MISS" }),
        ]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn good() -> Cost {
        // 60 samples a second apart, each spending 6 ms collecting, 0.3 % of a
        // core over the minute.
        Cost {
            elapsed_ms: 60_000.0,
            per_sample_ms: vec![6.0; 60],
            cpu_ms: Some(180.0),
        }
    }

    #[test]
    fn a_clean_run_passes() {
        let verdict = Verdict::judge(61, 1000, &good());
        assert_eq!(verdict.target_hz, 1.0);
        assert!((verdict.rate_hz - 1.0).abs() < 0.001);
        assert!(verdict.rate_ok);
        assert_eq!(verdict.mean_ms, 6.0);
        assert!(verdict.sample_ok);
        assert!(verdict.cpu_ok);
        assert!(verdict.passed());
        assert_eq!(
            verdict.render(),
            [
                "budget".to_owned(),
                "  rate       1.00 Hz of 1.00 Hz over 61 samples — ok".to_owned(),
                "  collection mean 6.0 ms, worst 6.0 ms, ceiling 1000 ms — ok".to_owned(),
                "  cpu        0.30 % of one core, ceiling 1 % — ok".to_owned(),
                "  verdict    PASS".to_owned(),
            ]
        );
    }

    #[test]
    fn a_slow_sample_fails_the_run() {
        let mut cost = good();
        cost.per_sample_ms[7] = 1_400.0; // over the interval itself
        let verdict = Verdict::judge(61, 1000, &cost);
        assert!(!verdict.sample_ok);
        assert!(!verdict.passed());
        assert!(verdict.render()[3].contains("OVER"));
    }

    #[test]
    fn a_run_that_drifted_fails_the_rate() {
        // 61 samples but 90 seconds of wall clock: 0.67 Hz, not 1.
        let cost = Cost { elapsed_ms: 90_000.0, ..good() };
        let verdict = Verdict::judge(61, 1000, &cost);
        assert!((verdict.rate_hz - 0.667).abs() < 0.01);
        assert!(!verdict.rate_ok);
        assert!(!verdict.passed());
    }

    #[test]
    fn a_greedy_process_fails_the_cpu_share() {
        // 1.2 s of CPU over the minute is 2 % of one core.
        let cost = Cost { cpu_ms: Some(1_200.0), ..good() };
        let verdict = Verdict::judge(61, 1000, &cost);
        assert!(!verdict.cpu_ok);
        assert!(!verdict.passed());
    }

    #[test]
    fn an_unmeasured_cpu_cost_does_not_fail_and_does_not_pass_silently() {
        let cost = Cost { cpu_ms: None, ..good() };
        let verdict = Verdict::judge(61, 1000, &cost);
        assert!(verdict.cpu_ok);
        assert!(verdict.passed());
        assert_eq!(verdict.render()[3], "  cpu        — (not measurable on this platform)");
    }

    #[test]
    fn one_sample_has_no_rate_to_hold() {
        let cost = Cost { elapsed_ms: 4.0, per_sample_ms: vec![4.0], cpu_ms: Some(1.0) };
        let verdict = Verdict::judge(1, 1000, &cost);
        assert_eq!(verdict.rate_hz, 0.0);
        assert!(verdict.rate_ok);
        assert!(verdict.passed());
    }

    #[test]
    fn an_empty_run_does_not_divide_by_zero() {
        let verdict = Verdict::judge(0, 1000, &Cost::default());
        assert_eq!(verdict.mean_ms, 0.0);
        assert!(verdict.passed());
    }
}
