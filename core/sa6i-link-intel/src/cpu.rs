// SPDX-License-Identifier: MPL-2.0
//! Per-process CPU: a rate between two readings of the same process.
//!
//! The arithmetic is the easy half. The half that goes wrong in shipping
//! software is identity: Windows hands a pid to a new process as soon as the old
//! one exits, so a map keyed by pid alone credits one program with another's
//! CPU — the kind of error that produces a confident, wrong answer. A key here
//! is the pid *and* the process's creation stamp, so a recycled pid is a
//! different process and its first reading is `NotSampledYet`, not a number.
//!
//! Percent is of one core, which is what Windows' own per-process counter
//! reports: a process using four threads flat out reads 400 %. Dividing by the
//! core count to make a share of the machine is the caller's decision, and the
//! Monitor does not make it.

use std::collections::{HashMap, HashSet};

use crate::model::{MetricState, WhyUnknown};

/// Who a reading belongs to.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct ProcessKey {
    pub pid: u32,
    /// When the process started, in whatever unit the collector counts in. Only
    /// equality matters: two readings with the same key are the same process.
    pub created: u64,
}

#[derive(Debug, Clone, Copy)]
struct Reading {
    at_ms: u64,
    cpu_ms: u64,
}

/// The previous reading of each process, so the next one can be a rate.
#[derive(Debug, Default)]
pub struct ProcessCpu {
    previous: HashMap<ProcessKey, Reading>,
}

impl ProcessCpu {
    /// The share of one core `key` has used since its last reading.
    ///
    /// `Unknown(NotSampledYet)` for a process seen for the first time, and for
    /// one read twice in the same millisecond: a rate needs two moments, and a
    /// span of zero is not one.
    pub fn percent(&mut self, key: ProcessKey, at_ms: u64, cpu_ms: u64) -> MetricState<f32> {
        let now = Reading { at_ms, cpu_ms };
        match self.previous.insert(key, now) {
            Some(before) => rate(before, now),
            None => MetricState::Unknown(WhyUnknown::NotSampledYet),
        }
    }

    /// Forget everything that was not in this round.
    ///
    /// Without this the map grows with every program the user opens and closes.
    pub fn retain(&mut self, keys: impl IntoIterator<Item = ProcessKey>) {
        let live: HashSet<ProcessKey> = keys.into_iter().collect();
        self.previous.retain(|key, _| live.contains(key));
    }

    /// How many processes are being tracked, for tests and for a log line.
    pub fn tracked(&self) -> usize {
        self.previous.len()
    }
}

fn rate(before: Reading, now: Reading) -> MetricState<f32> {
    let wall = now.at_ms.saturating_sub(before.at_ms);
    if wall == 0 {
        return MetricState::Unknown(WhyUnknown::NotSampledYet);
    }
    // A counter that went backwards is not a rate. Saturating to zero says
    // "nothing used" rather than inventing a negative or a wrap-around.
    let cpu = now.cpu_ms.saturating_sub(before.cpu_ms);
    MetricState::Value((cpu as f64 / wall as f64 * 100.0) as f32)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn key(pid: u32, created: u64) -> ProcessKey {
        ProcessKey { pid, created }
    }

    #[test]
    fn a_rate_needs_two_readings() {
        let mut cpu = ProcessCpu::default();
        let one = key(4242, 100);
        assert_eq!(cpu.percent(one, 1_000, 500), MetricState::Unknown(WhyUnknown::NotSampledYet));
        // 10 ms of CPU over one second is one percent of one core.
        assert_eq!(cpu.percent(one, 2_000, 510), MetricState::Value(1.0));
    }

    #[test]
    fn a_busy_process_may_exceed_one_core() {
        let mut cpu = ProcessCpu::default();
        let it = key(7, 1);
        cpu.percent(it, 0, 0);
        // 2.5 s of CPU in one second: four threads busy.
        assert_eq!(cpu.percent(it, 1_000, 2_500), MetricState::Value(250.0));
    }

    #[test]
    fn the_same_moment_is_not_a_span() {
        let mut cpu = ProcessCpu::default();
        let it = key(9, 1);
        cpu.percent(it, 5_000, 100);
        assert_eq!(cpu.percent(it, 5_000, 120), MetricState::Unknown(WhyUnknown::NotSampledYet));
    }

    #[test]
    fn a_counter_that_went_backwards_is_not_a_negative_rate() {
        let mut cpu = ProcessCpu::default();
        let it = key(11, 1);
        cpu.percent(it, 0, 5_000);
        assert_eq!(cpu.percent(it, 1_000, 4_000), MetricState::Value(0.0));
    }

    #[test]
    fn a_recycled_pid_is_a_different_process() {
        let mut cpu = ProcessCpu::default();
        // Same pid, different creation stamp: the second one has never been
        // seen before, and must not inherit the first one's rate.
        cpu.percent(key(1234, 500), 0, 1_000);
        assert_eq!(
            cpu.percent(key(1234, 900), 1_000, 2_000),
            MetricState::Unknown(WhyUnknown::NotSampledYet)
        );
        // And the new process gets a real rate on its second reading.
        assert_eq!(cpu.percent(key(1234, 900), 2_000, 2_050), MetricState::Value(5.0));
    }

    #[test]
    fn processes_that_went_away_are_forgotten() {
        let mut cpu = ProcessCpu::default();
        let stays = key(1, 1);
        let goes = key(2, 1);
        cpu.percent(stays, 0, 0);
        cpu.percent(goes, 0, 0);
        assert_eq!(cpu.tracked(), 2);
        cpu.retain([stays]);
        assert_eq!(cpu.tracked(), 1);
        // The one that went away starts over if it ever comes back.
        assert_eq!(cpu.percent(goes, 1_000, 10), MetricState::Unknown(WhyUnknown::NotSampledYet));
    }
}
