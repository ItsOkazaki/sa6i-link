// SPDX-License-Identifier: MPL-2.0
//! The sample store: a bounded history of snapshots.
//!
//! Slice 1 keeps this in memory. Persistence (SQLite rollups with the retention
//! table from `docs/architecture/INTELLIGENCE-CORE.md` §9) arrives with the
//! Monitor page's history view; the interface here is what makes that swap a
//! change of one type and not of every rule.

use std::collections::VecDeque;

use crate::model::{Snapshot, Timestamp};

/// How many snapshots to keep by default.
///
/// At the collector's 1 Hz this is a bit over an hour of raw history — enough
/// for every "sustained for N minutes" rule slice 1 ships, and small enough
/// that the whole history is a few megabytes.
pub const DEFAULT_CAPACITY: usize = 4096;

/// A bounded ring of snapshots, oldest first.
#[derive(Debug, Clone)]
pub struct SampleStore {
    samples: VecDeque<Snapshot>,
    capacity: usize,
}

impl Default for SampleStore {
    fn default() -> Self {
        Self::with_capacity(DEFAULT_CAPACITY)
    }
}

impl SampleStore {
    /// A store that keeps at most `capacity` snapshots.
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            samples: VecDeque::with_capacity(capacity.min(DEFAULT_CAPACITY)),
            capacity: capacity.max(2),
        }
    }

    /// Add a snapshot, dropping the oldest when full.
    pub fn push(&mut self, snapshot: Snapshot) {
        if self.samples.len() == self.capacity {
            self.samples.pop_front();
        }
        self.samples.push_back(snapshot);
    }

    /// The newest snapshot.
    pub fn latest(&self) -> Option<&Snapshot> {
        self.samples.back()
    }

    /// Every snapshot, oldest first.
    pub fn samples(&self) -> impl Iterator<Item = &Snapshot> {
        self.samples.iter()
    }

    pub fn len(&self) -> usize {
        self.samples.len()
    }

    pub fn is_empty(&self) -> bool {
        self.samples.is_empty()
    }

    /// How long the store covers, in milliseconds of monotonic time.
    pub fn span_ms(&self) -> u64 {
        match (self.samples.front(), self.samples.back()) {
            (Some(first), Some(last)) => last.monotonic_ms.saturating_sub(first.monotonic_ms),
            _ => 0,
        }
    }

    /// Whether `holds` was true of **every** snapshot in the last `window_ms`,
    /// and how long that has been the case.
    ///
    /// This is the hysteresis every "sustained" rule needs: a single spike is
    /// not a finding, and a rule that fires on one is a rule the user learns to
    /// ignore. Returns `None` when the store does not yet cover the window —
    /// not covering it is not the same as passing it.
    pub fn held_for(
        &self,
        window_ms: u64,
        mut holds: impl FnMut(&Snapshot) -> bool,
    ) -> Option<HeldWindow> {
        let last = self.samples.back()?;
        // A window the store does not span cannot be satisfied, no matter what
        // the samples inside it say. Without this, a two-minute history answers
        // a ten-minute question by silently treating the start of history as
        // the start of the window — which is how a spike becomes a "trend".
        if self.span_ms() < window_ms {
            return None;
        }
        let end = last.monotonic_ms;
        let start = end.saturating_sub(window_ms);
        if self.samples.front()?.monotonic_ms > start {
            return None;
        }
        // Walking backwards from the newest sample: the first one is the end of
        // the window, the last one is its start.
        let mut from_seq: Option<u64> = None;
        let mut to_seq: Option<u64> = None;
        for sample in self.samples.iter().rev() {
            if sample.monotonic_ms < start {
                break;
            }
            if !holds(sample) {
                return None;
            }
            if to_seq.is_none() {
                to_seq = Some(sample.seq);
            }
            from_seq = Some(sample.seq);
        }
        Some(HeldWindow {
            from_seq: from_seq?,
            to_seq: to_seq?,
            held_for_ms: window_ms,
        })
    }

    /// Drop snapshots older than `older_than` on the monotonic clock.
    pub fn prune_before(&mut self, monotonic_ms: u64) {
        while let Some(front) = self.samples.front() {
            if front.monotonic_ms < monotonic_ms {
                self.samples.pop_front();
            } else {
                break;
            }
        }
    }

    /// Wall-clock time of the newest snapshot, for "first seen" bookkeeping.
    pub fn last_seen(&self) -> Option<Timestamp> {
        self.samples.back().map(|s| s.taken_at)
    }
}

/// The result of a hysteresis check.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct HeldWindow {
    pub from_seq: u64,
    pub to_seq: u64,
    pub held_for_ms: u64,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{
        Bytes, CpuSample, MemorySample, MetricState, VolumeKind, VolumeSample, WhyUnknown,
    };

    fn snapshot(seq: u64, monotonic_ms: u64, cpu: f32, disk_used: f32) -> Snapshot {
        Snapshot {
            seq,
            taken_at: Timestamp(seq as i64 * 1000),
            monotonic_ms,
            cpu: CpuSample { percent: MetricState::Value(cpu) },
            memory: MemorySample {
                total: MetricState::Value(Bytes(1000)),
                available: MetricState::Value(Bytes(500)),
                commit_limit: MetricState::Unknown(WhyUnknown::NotCollectedYet),
                commit_used: MetricState::Unknown(WhyUnknown::NotCollectedYet),
            },
            volumes: vec![VolumeSample {
                mount: "C:\\".to_owned(),
                kind: VolumeKind::Fixed,
                total: MetricState::Value(Bytes(100)),
                free: MetricState::Value(Bytes((100.0 - disk_used) as u64)),
            }],
            uptime: MetricState::Value(60),
        }
    }

    #[test]
    fn the_ring_drops_the_oldest_and_never_grows() {
        let mut store = SampleStore::with_capacity(3);
        for seq in 1..=5 {
            store.push(snapshot(seq, seq * 1000, 10.0, 50.0));
        }
        assert_eq!(store.len(), 3);
        let seqs: Vec<u64> = store.samples().map(|s| s.seq).collect();
        assert_eq!(seqs, vec![3, 4, 5]);
        assert_eq!(store.latest().map(|s| s.seq), Some(5));
    }

    fn busy(sample: &Snapshot) -> bool {
        sample.cpu.percent.value().is_some_and(|p| *p > 90.0)
    }

    #[test]
    fn a_window_the_store_cannot_cover_is_not_a_pass() {
        let mut store = SampleStore::with_capacity(64);
        store.push(snapshot(1, 0, 10.0, 50.0));
        store.push(snapshot(2, 1000, 10.0, 50.0));
        // A second of history cannot answer a ten-minute question.
        assert_eq!(store.held_for(600_000, |s| s.cpu.percent.is_known()), None);
        // It can answer a one-second one, and both samples are inside it.
        assert_eq!(
            store.held_for(1000, |s| s.cpu.percent.is_known()),
            Some(HeldWindow { from_seq: 1, to_seq: 2, held_for_ms: 1000 })
        );
    }

    #[test]
    fn one_bad_sample_breaks_the_window() {
        let mut store = SampleStore::with_capacity(64);
        store.push(snapshot(1, 0, 12.0, 50.0)); // quiet
        store.push(snapshot(2, 1000, 95.0, 50.0));
        store.push(snapshot(3, 2000, 95.0, 50.0));
        store.push(snapshot(4, 3000, 95.0, 50.0));
        // The last two seconds were busy throughout.
        assert_eq!(
            store.held_for(2000, busy),
            Some(HeldWindow { from_seq: 2, to_seq: 4, held_for_ms: 2000 })
        );
        // Reaching back to the quiet sample disqualifies the whole window.
        assert_eq!(store.held_for(3000, busy), None);
    }

    #[test]
    fn pruning_keeps_the_newest() {
        let mut store = SampleStore::with_capacity(64);
        for seq in 1..=5 {
            store.push(snapshot(seq, seq * 1000, 10.0, 50.0));
        }
        store.prune_before(4000);
        let seqs: Vec<u64> = store.samples().map(|s| s.seq).collect();
        assert_eq!(seqs, vec![4, 5]);
        assert_eq!(store.span_ms(), 1000);
    }
}
