// SPDX-License-Identifier: MPL-2.0
//! A window of samples, averaged — the form M1's two machine checks need.
//!
//! Both of the checks that need a real PC ask the same question in different
//! clothes: *what was the average over a minute, and how many samples had a
//! reading?* Task Manager shows 60 seconds of CPU and memory; a sampling budget
//! is meaningless without knowing how many of the moments were measured. So the
//! arithmetic lives here, where it is tested, and the command line prints it.
//!
//! The rule from the model carries over: an unmeasured sample is excluded from
//! the mean and *counted*, never averaged in as zero. A machine whose collector
//! failed every other second would otherwise look idle.

use serde::Serialize;

use crate::findings::{human_duration, render_percent};
use crate::model::Snapshot;

/// The mean of a window's readings, and how many of them there were.
#[derive(Debug, Clone, Copy, PartialEq, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Average {
    /// Mean over the measured samples only. `None` when nothing was measured.
    pub mean: Option<f32>,
    /// How many samples carried a reading.
    pub measured: usize,
    /// How many samples the window held.
    pub of: usize,
}

impl Average {
    /// Average the readings in `states`, skipping the ones without one.
    pub fn of(states: impl IntoIterator<Item = Option<f32>>) -> Self {
        let mut total = 0.0_f64;
        let mut measured = 0usize;
        let mut count = 0usize;
        for state in states {
            count += 1;
            if let Some(value) = state {
                total += f64::from(value);
                measured += 1;
            }
        }
        Self {
            mean: (measured > 0).then(|| (total / measured as f64) as f32),
            measured,
            of: count,
        }
    }

    /// How many samples could not be read.
    pub fn missing(&self) -> usize {
        self.of.saturating_sub(self.measured)
    }

    /// `"12.4 % (60 of 60 samples)"`, or why there is nothing to average.
    pub fn render(&self) -> String {
        match self.mean {
            Some(mean) => format!("{} ({} of {} samples)", render_percent(mean), self.measured, self.of),
            None => format!("— (nothing measured of {} samples)", self.of),
        }
    }
}

/// What a window of samples came to.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WindowSummary {
    /// How many samples the window held.
    pub samples: usize,
    /// Monotonic milliseconds from the first sample to the last.
    pub span_ms: u64,
    pub cpu: Average,
    pub memory: Average,
}

impl WindowSummary {
    /// Summarise samples that are oldest first.
    pub fn of(samples: &[Snapshot]) -> Self {
        let span_ms = match (samples.first(), samples.last()) {
            (Some(first), Some(last)) => last.monotonic_ms.saturating_sub(first.monotonic_ms),
            _ => 0,
        };
        Self {
            samples: samples.len(),
            span_ms,
            cpu: Average::of(samples.iter().map(|sample| sample.cpu.percent.value().copied())),
            memory: Average::of(
                samples.iter().map(|sample| sample.memory.percent_used().value().copied()),
            ),
        }
    }

    /// One line a person can compare with Task Manager.
    pub fn line(&self) -> String {
        format!(
            "cpu {} · memory {} · over {}",
            self.cpu.render(),
            self.memory.render(),
            human_duration(self.span_ms)
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{
        Bytes, CpuSample, DiskIoSample, MemorySample, MetricState, Timestamp, WhyUnknown,
    };

    fn bytes(value: u64) -> MetricState<Bytes> {
        MetricState::Value(Bytes(value))
    }

    fn sample(seq: u64, cpu: MetricState<f32>, available: MetricState<Bytes>) -> Snapshot {
        Snapshot {
            seq,
            taken_at: Timestamp(1_700_000_000_000 + seq as i64 * 1000),
            monotonic_ms: seq * 1000,
            cpu: CpuSample { percent: cpu, per_core: Vec::new() },
            memory: MemorySample {
                total: bytes(16 * 1024 * 1024 * 1024),
                available,
                commit_limit: bytes(20 * 1024 * 1024 * 1024),
                commit_used: bytes(9 * 1024 * 1024 * 1024),
                pages_input_per_second: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            },
            volumes: Vec::new(),
            disk_io: DiskIoSample::unavailable(WhyUnknown::NotCollectedYet),
            gpu: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            processes: Vec::new(),
            uptime: MetricState::Value(3_600),
        }
    }

    #[test]
    fn a_mean_uses_only_what_was_measured_and_says_so() {
        let avg = Average::of([Some(10.0), None, Some(30.0)]);
        assert_eq!(avg.mean, Some(20.0));
        assert_eq!((avg.measured, avg.of), (2, 3));
        assert_eq!(avg.missing(), 1);
        assert_eq!(avg.render(), "20.0 % (2 of 3 samples)");
    }

    #[test]
    fn nothing_measured_is_not_a_zero() {
        let avg = Average::of([None, None]);
        assert_eq!(avg.mean, None);
        assert_eq!(avg.render(), "— (nothing measured of 2 samples)");
        // The empty window is the same answer, not a divide by zero.
        let empty = WindowSummary::of(&[]);
        assert_eq!(empty.cpu.mean, None);
        assert_eq!(empty.span_ms, 0);
    }

    #[test]
    fn the_span_runs_from_the_first_sample_to_the_last() {
        let samples: Vec<Snapshot> = (1..=4)
            .map(|seq| sample(seq, MetricState::Value(50.0), bytes(8 * 1024 * 1024 * 1024)))
            .collect();
        let summary = WindowSummary::of(&samples);
        assert_eq!(summary.samples, 4);
        assert_eq!(summary.span_ms, 3_000);
        assert_eq!(summary.cpu.measured, 4);
        assert_eq!(
            summary.line(),
            "cpu 50.0 % (4 of 4 samples) · memory 50.0 % (4 of 4 samples) · over 3 seconds"
        );
    }

    #[test]
    fn a_window_with_gaps_averages_the_samples_it_has() {
        let samples = vec![
            sample(1, MetricState::Value(10.0), bytes(8 * 1024 * 1024 * 1024)),
            // The first second cannot know a rate.
            sample(2, MetricState::Unknown(WhyUnknown::NotSampledYet), bytes(4 * 1024 * 1024 * 1024)),
            // Memory unreadable that second.
            sample(
                3,
                MetricState::Value(30.0),
                MetricState::Unknown(WhyUnknown::CollectorFailed),
            ),
        ];
        let summary = WindowSummary::of(&samples);
        assert_eq!(summary.cpu.mean, Some(20.0));
        assert_eq!(summary.cpu.missing(), 1);
        // Memory: 50 % used, then 75 %, then unreadable — averaged over the two
        // that were measured, not over three with a zero in the middle.
        assert_eq!(summary.memory.measured, 2);
        assert_eq!(summary.memory.mean, Some(62.5));
    }
}
