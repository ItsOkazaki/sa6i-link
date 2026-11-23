// SPDX-License-Identifier: MPL-2.0
//! Findings and their evidence.
//!
//! A [`Finding`] is the only thing the UI is allowed to call a problem. It
//! exists only if a rule produced it from measured data, and it carries that
//! data with it — so "why does Sa6i say this?" is answered from the snapshot,
//! not from a sentence someone wrote once.

use serde::{Deserialize, Serialize};

use crate::model::{Snapshot, Timestamp, WhyUnknown};

/// How much the user should care.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Severity {
    /// Worth knowing, nothing to do.
    Info,
    /// Worth knowing, probably worth doing something about.
    Notice,
    /// Something is degrading the machine now or soon.
    Warning,
    /// Data loss or a broken machine is plausible if ignored.
    Critical,
}

impl Severity {
    /// A word for the screen, so severity is never carried by colour alone.
    pub fn label(self) -> &'static str {
        match self {
            Self::Info => "Info",
            Self::Notice => "Notice",
            Self::Warning => "Warning",
            Self::Critical => "Critical",
        }
    }

    /// The token role the UI paints this with.
    pub fn tone(self) -> &'static str {
        match self {
            Self::Info | Self::Notice => "primary",
            Self::Warning => "warning",
            Self::Critical => "error",
        }
    }
}

/// How sure the rule is, given how much it measured.
///
/// Deliberately coarse: three levels a person can act on, not a fake
/// probability.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Confidence {
    /// Measured directly, above the threshold, for the whole window.
    Certain,
    /// Measured, but on a short window or from a single sample.
    Likely,
    /// A signal that suggests a cause rather than proving one.
    Possible,
}

/// One piece of measured data behind a finding.
///
/// `sample_seq` is what makes this checkable: those snapshots can be printed,
/// exported or attached to a bug report and the finding re-derived from them.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Evidence {
    /// Metric path, e.g. `volume.C.percent_used` — the same string the UI shows.
    pub metric: String,
    /// Rendered observed value with its unit, e.g. `"94.2 %"`.
    pub observed: String,
    /// The threshold that was crossed, rendered the same way.
    pub threshold: Option<String>,
    /// The sample range this came from.
    pub from_seq: u64,
    pub to_seq: u64,
    /// How long the condition had held when the finding was made.
    pub held_for_ms: u64,
}

impl Evidence {
    /// Build evidence for a metric measured in the newest snapshot.
    pub fn new(metric: impl Into<String>, observed: impl Into<String>) -> Self {
        Self {
            metric: metric.into(),
            observed: observed.into(),
            threshold: None,
            from_seq: 0,
            to_seq: 0,
            held_for_ms: 0,
        }
    }

    pub fn threshold(mut self, threshold: impl Into<String>) -> Self {
        self.threshold = Some(threshold.into());
        self
    }

    pub fn over(mut self, from_seq: u64, to_seq: u64, held_for_ms: u64) -> Self {
        self.from_seq = from_seq;
        self.to_seq = to_seq;
        self.held_for_ms = held_for_ms;
        self
    }

    /// The one-line explanation the UI shows above the numbers.
    pub fn sentence(&self) -> String {
        match (&self.threshold, self.from_seq) {
            (Some(threshold), seq) if seq > 0 => format!(
                "{} was {} (threshold {}), for {}",
                self.metric,
                self.observed,
                threshold,
                human_duration(self.held_for_ms)
            ),
            (Some(threshold), _) => {
                format!("{} is {} (threshold {})", self.metric, self.observed, threshold)
            }
            (None, _) => format!("{} is {}", self.metric, self.observed),
        }
    }
}

/// A problem, with the data that proves it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Finding {
    /// Stable id: `"<rule>/<subject>"`. Two runs on the same machine agree, so
    /// dismissing or re-reading a finding does not depend on ordering.
    pub id: String,
    /// The rule that produced it.
    pub rule: String,
    pub severity: Severity,
    pub confidence: Confidence,
    /// The thing it is about: a volume letter, a process name, `"system"`.
    pub subject: String,
    /// A short title, safe to show as-is.
    pub title: String,
    /// One or two sentences in plain language, deterministic, always present.
    pub explain: String,
    /// The measurements behind it; never empty.
    pub evidence: Vec<Evidence>,
    /// Registered action ids the user may take. Never executed automatically.
    pub actions: Vec<String>,
    /// When this rule first and last saw it, within the store's retention.
    pub first_seen: Timestamp,
    pub last_seen: Timestamp,
    /// The snapshot that produced this evaluation.
    pub snapshot_seq: u64,
}

impl Finding {
    /// Whether the finding carries the measurements it claims to.
    ///
    /// Used as an assertion: a finding without evidence is a bug, and the rule
    /// engine drops it rather than showing the user a claim.
    pub fn is_supported(&self) -> bool {
        !self.evidence.is_empty() && self.evidence.iter().all(|e| !e.metric.is_empty())
    }
}

/// Renders a duration the way a person says it: "3 days", "12 minutes".
pub fn human_duration(ms: u64) -> String {
    let seconds = ms / 1000;
    let (count, unit) = match seconds {
        0..=59 => (seconds.max(1), "second"),
        60..=3599 => (seconds / 60, "minute"),
        3600..=86_399 => (seconds / 3600, "hour"),
        _ => (seconds / 86_400, "day"),
    };
    if count == 1 {
        format!("1 {unit}")
    } else {
        format!("{count} {unit}s")
    }
}

/// `"94.2 %"`, `"12.4 GB"`, `"3 days"`.
pub fn render_percent(value: f32) -> String {
    format!("{value:.1} %")
}

/// Bytes for humans, in the units Windows shows in Explorer.
pub fn render_bytes(bytes: u64) -> String {
    const UNITS: [&str; 5] = ["bytes", "KB", "MB", "GB", "TB"];
    let mut value = bytes as f64;
    let mut unit = 0;
    while value >= 1024.0 && unit + 1 < UNITS.len() {
        value /= 1024.0;
        unit += 1;
    }
    if unit == 0 {
        format!("{} {}", bytes, UNITS[unit])
    } else {
        format!("{value:.1} {}", UNITS[unit])
    }
}

/// The one sentence a snapshot can say about itself when nothing is wrong.
///
/// Written down here so the "all clear" path is a decision, not an accident:
/// it names what was measured and what could not be, and never claims the
/// machine is healthy.
pub fn all_clear_sentence(snapshot: &Snapshot) -> String {
    let measured = snapshot.metrics().len();
    let unreadable: Vec<&'static str> = [
        snapshot.cpu.percent.why(),
        snapshot.memory.percent_used().why(),
        snapshot.uptime.why(),
    ]
    .into_iter()
    .flatten()
    .map(WhyUnknown::explain)
    .collect();
    if unreadable.is_empty() {
        format!("Nothing needs attention. {measured} measurements are current.")
    } else {
        format!(
            "Nothing needs attention from {measured} measurements. Not readable: {}.",
            unreadable.join("; ")
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn durations_read_like_a_person_wrote_them() {
        assert_eq!(human_duration(1_000), "1 second");
        assert_eq!(human_duration(30_000), "30 seconds");
        assert_eq!(human_duration(60_000), "1 minute");
        assert_eq!(human_duration(12 * 60_000), "12 minutes");
        assert_eq!(human_duration(3_600_000), "1 hour");
        assert_eq!(human_duration(3 * 86_400_000), "3 days");
    }

    #[test]
    fn bytes_use_the_units_a_user_sees_in_explorer() {
        assert_eq!(render_bytes(512), "512 bytes");
        assert_eq!(render_bytes(1024), "1.0 KB");
        assert_eq!(render_bytes(12_400_000_000), "11.5 GB");
    }

    #[test]
    fn evidence_sentences_are_checkable() {
        let e = Evidence::new("volume.C.percent_used", "94.2 %")
            .threshold("90.0 %")
            .over(10, 40, 600_000);
        assert_eq!(
            e.sentence(),
            "volume.C.percent_used was 94.2 % (threshold 90.0 %), for 10 minutes"
        );
        let fresh = Evidence::new("volume.C.percent_used", "94.2 %").threshold("90.0 %");
        assert_eq!(fresh.sentence(), "volume.C.percent_used is 94.2 % (threshold 90.0 %)");
    }

    #[test]
    fn a_finding_without_evidence_is_not_supported() {
        let mut finding = Finding {
            id: "x/y".into(),
            rule: "x".into(),
            severity: Severity::Warning,
            confidence: Confidence::Certain,
            subject: "y".into(),
            title: "t".into(),
            explain: "e".into(),
            evidence: Vec::new(),
            actions: Vec::new(),
            first_seen: Timestamp(0),
            last_seen: Timestamp(0),
            snapshot_seq: 1,
        };
        assert!(!finding.is_supported());
        finding.evidence.push(Evidence::new("cpu.percent", "94.0 %"));
        assert!(finding.is_supported());
    }

    #[test]
    fn severity_never_relies_on_colour_alone() {
        for severity in [Severity::Info, Severity::Notice, Severity::Warning, Severity::Critical] {
            assert!(!severity.label().is_empty());
            assert!(matches!(severity.tone(), "primary" | "warning" | "error"));
        }
    }
}
