// SPDX-License-Identifier: MPL-2.0
//! Durable history: the samples and findings that outlive a run.
//!
//! The in-memory ring ([`crate::SampleStore`]) answers "what happened in the
//! last hour". This answers "what happened last week", which is the difference
//! between a dashboard and a diagnosis: "96 % full right now" is a fact, "96 %
//! full for three weeks" is the thing worth telling someone about.
//!
//! Storage is SQLite in the app's data directory. One row per minute for raw
//! samples, not one per second: a day is 1,440 rows and a few hundred kilobytes,
//! while the second that a rule needed is already in the ring. Findings are kept
//! as upserts keyed by their stable id, so `first_seen` is the first time this
//! machine ever had that problem and `last_seen` is the most recent.

use std::{fmt, path::Path, time::Duration};

use rusqlite::{Connection, OptionalExtension, params};
use serde_json::Error as JsonError;

use crate::findings::Finding;
use crate::model::{Snapshot, Timestamp};

/// How often raw samples are written: once a minute.
pub const RECORD_INTERVAL_MS: i64 = 60_000;

/// Raw samples are kept for a day.
const RAW_RETENTION_MS: i64 = 24 * 60 * 60 * 1000;
/// Findings are kept for a month, because a recurring problem is information.
const FINDING_RETENTION_MS: i64 = 30 * 24 * 60 * 60 * 1000;

/// The schema version this build writes. A database made by a newer build is
/// refused rather than silently mis-read.
const SCHEMA_VERSION: i64 = 1;

/// Anything that can go wrong while keeping history.
#[derive(Debug)]
pub enum HistoryError {
    /// SQLite said no.
    Database(rusqlite::Error),
    /// A stored row did not parse as the snapshot or finding it claims to be.
    Corrupt(JsonError),
    /// The file was written by a newer Sa6i.
    NewerSchema(i64),
}

impl fmt::Display for HistoryError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Database(error) => write!(f, "history database: {error}"),
            Self::Corrupt(error) => write!(f, "stored history is not readable: {error}"),
            Self::NewerSchema(version) => write!(
                f,
                "this history was written by a newer Sa6i (schema {version}); \
                 it was left untouched"
            ),
        }
    }
}

impl std::error::Error for HistoryError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Database(error) => Some(error),
            Self::Corrupt(error) => Some(error),
            Self::NewerSchema(_) => None,
        }
    }
}

impl From<rusqlite::Error> for HistoryError {
    fn from(error: rusqlite::Error) -> Self {
        Self::Database(error)
    }
}

impl From<JsonError> for HistoryError {
    fn from(error: JsonError) -> Self {
        Self::Corrupt(error)
    }
}

/// The durable record of what this machine did.
#[derive(Debug)]
pub struct History {
    conn: Connection,
    /// Wall-clock time of the newest stored sample, so the once-a-minute rule
    /// survives a restart instead of writing a burst on launch.
    last_recorded_at: Option<i64>,
}

impl History {
    /// Open (or create) the history at `path`.
    pub fn open(path: &Path) -> Result<Self, HistoryError> {
        if let Some(parent) = path.parent() {
            // A missing data directory is not a reason to have no history.
            let _ = std::fs::create_dir_all(parent);
        }
        Self::from_connection(Connection::open(path)?)
    }

    /// A history in memory, for tests and for a machine where the disk is not
    /// writable: the same code paths, no file.
    pub fn open_in_memory() -> Result<Self, HistoryError> {
        Self::from_connection(Connection::open_in_memory()?)
    }

    fn from_connection(conn: Connection) -> Result<Self, HistoryError> {
        conn.busy_timeout(Duration::from_secs(2))?;
        // WAL keeps a reader (the UI) from blocking the recorder (the sampler).
        // In-memory databases report "memory" and ignore it.
        let _ = conn.execute_batch("PRAGMA journal_mode=WAL;");
        let mut history = Self { conn, last_recorded_at: None };
        history.migrate()?;
        history.last_recorded_at = history.newest_sample_at()?;
        Ok(history)
    }

    fn migrate(&mut self) -> Result<(), HistoryError> {
        let version: i64 = self.conn.query_row("PRAGMA user_version", [], |row| row.get(0))?;
        if version > SCHEMA_VERSION {
            return Err(HistoryError::NewerSchema(version));
        }
        if version == SCHEMA_VERSION {
            return Ok(());
        }
        self.conn.execute_batch(
            "BEGIN;
             CREATE TABLE IF NOT EXISTS sample (
                 taken_at    INTEGER PRIMARY KEY,
                 seq         INTEGER NOT NULL,
                 monotonic_ms INTEGER NOT NULL,
                 json        TEXT NOT NULL
             );
             CREATE TABLE IF NOT EXISTS finding (
                 id          TEXT PRIMARY KEY,
                 rule        TEXT NOT NULL,
                 severity    TEXT NOT NULL,
                 subject     TEXT NOT NULL,
                 title       TEXT NOT NULL,
                 first_seen  INTEGER NOT NULL,
                 last_seen   INTEGER NOT NULL,
                 json        TEXT NOT NULL
             );
             CREATE INDEX IF NOT EXISTS finding_last_seen ON finding (last_seen);
             PRAGMA user_version = 1;
             COMMIT;",
        )?;
        Ok(())
    }

    fn newest_sample_at(&self) -> Result<Option<i64>, HistoryError> {
        let sql = "SELECT MAX(taken_at) FROM sample";
        let row = self.conn.query_row(sql, [], |row| row.get::<_, Option<i64>>(0));
        Ok(row.optional()?.flatten())
    }

    /// Store a sample if the last one is at least a minute old.
    ///
    /// Returns whether a row was written. The caller can call this every second
    /// without thinking: that is what makes the recorder safe to run in the
    /// sampling loop.
    pub fn record(&mut self, snapshot: &Snapshot) -> Result<bool, HistoryError> {
        let mut taken_at = snapshot.taken_at.0;
        if let Some(last) = self.last_recorded_at {
            if taken_at < last {
                // The wall clock went backwards (a time sync, a manual change).
                // The sample is real, so it is stored as "the moment after the
                // last one" and `ORDER BY taken_at` keeps telling the truth.
                taken_at = last + 1;
            } else if taken_at - last < RECORD_INTERVAL_MS {
                return Ok(false);
            }
        }
        let json = serde_json::to_string(snapshot)?;
        self.conn.execute(
            "INSERT OR REPLACE INTO sample (taken_at, seq, monotonic_ms, json) VALUES (?1, ?2, ?3, ?4)",
            params![taken_at, snapshot.seq as i64, snapshot.monotonic_ms as i64, json],
        )?;
        self.last_recorded_at = Some(taken_at);
        Ok(true)
    }

    /// Remember findings, keeping when each was first and last seen.
    ///
    /// Idempotent: calling it every evaluation is the intended use.
    pub fn record_findings(&mut self, findings: &[Finding]) -> Result<(), HistoryError> {
        let tx = self.conn.transaction()?;
        for finding in findings {
            let json = serde_json::to_string(finding)?;
            tx.execute(
                "INSERT INTO finding (id, rule, severity, subject, title, first_seen, last_seen, json)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
                 ON CONFLICT(id) DO UPDATE SET
                     last_seen = excluded.last_seen,
                     json = excluded.json",
                params![
                    finding.id.as_str(),
                    finding.rule.as_str(),
                    finding.severity.label(),
                    finding.subject.as_str(),
                    finding.title.as_str(),
                    finding.first_seen.0,
                    finding.last_seen.0,
                    json,
                ],
            )?;
        }
        tx.commit()?;
        Ok(())
    }

    /// The newest `limit` samples, oldest first — the shape a chart wants.
    pub fn recent(&self, limit: usize) -> Result<Vec<Snapshot>, HistoryError> {
        let sql = "SELECT json FROM sample ORDER BY taken_at DESC LIMIT ?1";
        let mut statement = self.conn.prepare(sql)?;
        let rows = statement.query_map(params![limit as i64], |row| row.get::<_, String>(0))?;
        let mut samples = Vec::new();
        for row in rows {
            samples.push(serde_json::from_str::<Snapshot>(&row?)?);
        }
        samples.reverse();
        Ok(samples)
    }

    /// Findings still inside the retention window, worst first.
    pub fn findings(&self) -> Result<Vec<Finding>, HistoryError> {
        let sql = "SELECT json FROM finding ORDER BY last_seen DESC";
        let mut statement = self.conn.prepare(sql)?;
        let rows = statement.query_map([], |row| row.get::<_, String>(0))?;
        let mut findings = Vec::new();
        for row in rows {
            findings.push(serde_json::from_str::<Finding>(&row?)?);
        }
        findings.sort_by(|a, b| b.severity.cmp(&a.severity).then_with(|| a.id.cmp(&b.id)));
        Ok(findings)
    }

    /// When a finding was first seen on this machine, if it is still recorded.
    pub fn first_seen(&self, finding_id: &str) -> Result<Option<Timestamp>, HistoryError> {
        let sql = "SELECT first_seen FROM finding WHERE id = ?1";
        let found = self.conn.query_row(sql, params![finding_id], |row| row.get::<_, i64>(0));
        Ok(found.optional()?.map(Timestamp))
    }

    /// Drop raw samples older than a day and findings older than a month.
    ///
    /// Returns the number of rows removed, so a caller can log it once instead
    /// of guessing.
    pub fn prune(&mut self, now: Timestamp) -> Result<usize, HistoryError> {
        let raw_cutoff = now.0.saturating_sub(RAW_RETENTION_MS);
        let finding_cutoff = now.0.saturating_sub(FINDING_RETENTION_MS);
        let samples = self.conn.execute("DELETE FROM sample WHERE taken_at < ?1", params![raw_cutoff])?;
        let findings =
            self.conn.execute("DELETE FROM finding WHERE last_seen < ?1", params![finding_cutoff])?;
        if let Some(last) = self.last_recorded_at && last < raw_cutoff {
            self.last_recorded_at = None;
        }
        Ok(samples + findings)
    }

    /// How many samples and findings are stored, for a status line.
    pub fn counts(&self) -> Result<(usize, usize), HistoryError> {
        let samples: i64 = self.conn.query_row("SELECT COUNT(*) FROM sample", [], |row| row.get(0))?;
        let findings: i64 = self.conn.query_row("SELECT COUNT(*) FROM finding", [], |row| row.get(0))?;
        Ok((samples as usize, findings as usize))
    }

    /// Wall-clock time of the newest stored sample, as the file has it.
    pub fn newest_at(&self) -> Result<Option<Timestamp>, HistoryError> {
        Ok(self.newest_sample_at()?.map(Timestamp))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{
        Bytes, CpuSample, DiskIoSample, MemorySample, MetricState, VolumeKind, VolumeSample,
        WhyUnknown,
    };

    fn snapshot(seq: u64, taken_at: i64) -> Snapshot {
        Snapshot {
            seq,
            taken_at: Timestamp(taken_at),
            monotonic_ms: seq * 1000,
            cpu: CpuSample { percent: MetricState::Value(20.0), per_core: Vec::new() },
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
                free: MetricState::Value(Bytes(50)),
            }],
            disk_io: DiskIoSample::unavailable(WhyUnknown::NotCollectedYet),
            processes: Vec::new(),
            uptime: MetricState::Value(60),
        }
    }

    fn finding(id: &str, first: i64, last: i64) -> Finding {
        Finding {
            id: id.to_owned(),
            rule: "disk.low_free_space".to_owned(),
            severity: crate::findings::Severity::Warning,
            confidence: crate::findings::Confidence::Certain,
            subject: "C:".to_owned(),
            title: "Drive C: is almost full".to_owned(),
            explain: "because".to_owned(),
            evidence: vec![crate::findings::Evidence::new("volume.C.percent_used", "95.0 %")],
            actions: Vec::new(),
            first_seen: Timestamp(first),
            last_seen: Timestamp(last),
            snapshot_seq: 1,
        }
    }

    #[test]
    fn a_fresh_database_has_the_schema_and_no_rows() {
        let history = History::open_in_memory().unwrap();
        assert_eq!(history.counts().unwrap(), (0, 0));
        assert_eq!(history.newest_at().unwrap(), None);
        assert!(history.recent(10).unwrap().is_empty());
        assert!(history.findings().unwrap().is_empty());
    }

    #[test]
    fn samples_are_written_once_a_minute() {
        let mut history = History::open_in_memory().unwrap();
        assert!(history.record(&snapshot(1, 1_000_000)).unwrap());
        // A second later is inside the minute: no row, and no error.
        assert!(!history.record(&snapshot(2, 1_001_000)).unwrap());
        assert!(!history.record(&snapshot(3, 1_059_000)).unwrap());
        assert!(history.record(&snapshot(4, 1_060_000)).unwrap());
        assert_eq!(history.counts().unwrap().0, 2);
        assert_eq!(history.newest_at().unwrap(), Some(Timestamp(1_060_000)));
    }

    #[test]
    fn a_clock_that_goes_backwards_cannot_write_into_the_past() {
        let mut history = History::open_in_memory().unwrap();
        assert!(history.record(&snapshot(1, 5_000_000)).unwrap());
        // The wall clock jumps back an hour; the new sample still sorts after
        // the old one, so `ORDER BY taken_at` keeps telling the truth.
        assert!(history.record(&snapshot(2, 1_400_000)).unwrap());
        let stored = history.recent(10).unwrap();
        assert_eq!(stored.len(), 2);
        assert_eq!(stored[0].seq, 1);
        assert_eq!(stored[1].seq, 2);
    }

    #[test]
    fn recent_returns_oldest_first_and_respects_the_limit() {
        let mut history = History::open_in_memory().unwrap();
        for index in 0..5 {
            history.record(&snapshot(index + 1, 1_000_000 + (index as i64) * 60_000)).unwrap();
        }
        let recent = history.recent(3).unwrap();
        let seqs: Vec<u64> = recent.iter().map(|s| s.seq).collect();
        assert_eq!(seqs, vec![3, 4, 5], "the newest three, in plotting order");
    }

    #[test]
    fn history_survives_being_closed_and_reopened() {
        let dir = std::env::temp_dir().join(format!("sa6i-history-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let path = dir.join("history.db");
        {
            let mut history = History::open(&path).unwrap();
            let found = [finding("disk/C:", 1_000_000, 1_000_000)];
            assert!(history.record(&snapshot(1, 1_000_000)).unwrap());
            history.record_findings(&found).unwrap();
        }
        {
            let mut history = History::open(&path).unwrap();
            assert_eq!(history.counts().unwrap(), (1, 1));
            assert_eq!(history.newest_at().unwrap(), Some(Timestamp(1_000_000)));
            // The once-a-minute rule survives the restart: a sample one second
            // after the stored one is still inside the same minute.
            assert!(!history.record(&snapshot(2, 1_001_000)).unwrap());
            assert!(history.record(&snapshot(2, 1_060_000)).unwrap());
            let stored = history.recent(10).unwrap();
            assert_eq!(stored.len(), 2);
            assert_eq!(stored[1].seq, 2);
            assert_eq!(stored[1].memory.total, MetricState::Value(Bytes(1000)));
        }
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_finding_keeps_the_first_time_it_was_seen() {
        let mut history = History::open_in_memory().unwrap();
        history.record_findings(&[finding("disk/C:", 1_000, 1_000)]).unwrap();
        history.record_findings(&[finding("disk/C:", 999_999, 2_000_000)]).unwrap();
        assert_eq!(history.counts().unwrap().1, 1, "an upsert, not a second row");
        assert_eq!(history.first_seen("disk/C:").unwrap(), Some(Timestamp(1_000)));
        let stored = history.findings().unwrap();
        assert_eq!(stored.len(), 1);
        assert_eq!(stored[0].last_seen, Timestamp(2_000_000));
        assert_eq!(stored[0].severity, crate::findings::Severity::Warning);
    }

    #[test]
    fn pruning_removes_what_the_retention_table_says() {
        let mut history = History::open_in_memory().unwrap();
        let day = 24 * 60 * 60 * 1000i64;
        let now = Timestamp(10 * day);
        // One sample from two days ago, one from an hour ago.
        history.record(&snapshot(1, now.0 - 2 * day)).unwrap();
        history.record(&snapshot(2, now.0 - 3_600_000)).unwrap();
        // A finding last seen 40 days ago, and one seen today.
        history.record_findings(&[finding("old", now.0 - 40 * day, now.0 - 40 * day)]).unwrap();
        history.record_findings(&[finding("new", now.0 - 60_000, now.0 - 60_000)]).unwrap();
        assert_eq!(history.counts().unwrap(), (2, 2));

        let removed = history.prune(now).unwrap();
        assert_eq!(removed, 2);
        assert_eq!(history.counts().unwrap(), (1, 1));
        assert_eq!(history.findings().unwrap()[0].id, "new");
    }

    #[test]
    fn a_database_from_a_newer_sa6i_is_refused_rather_than_misread() {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch("PRAGMA user_version = 99;").unwrap();
        match History::from_connection(conn) {
            Err(HistoryError::NewerSchema(99)) => {}
            other => panic!("expected NewerSchema, got {other:?}"),
        }
    }

    #[test]
    fn the_interval_is_a_minute_of_wall_clock() {
        assert_eq!(RECORD_INTERVAL_MS, 60_000);
        assert!(RAW_RETENTION_MS > RECORD_INTERVAL_MS);
        assert!(FINDING_RETENTION_MS > RAW_RETENTION_MS);
    }
}
