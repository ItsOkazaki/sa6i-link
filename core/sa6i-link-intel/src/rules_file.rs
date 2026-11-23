// SPDX-License-Identifier: MPL-2.0
//! The TOML front-end: a rule's numbers as data, and the refusals that keep a
//! data file from inventing a rule.
//!
//! [`docs/plan/M2-RULES.md`] sets the shape of this. A file may change a
//! threshold, a window, and restate four words that the code already decides —
//! and it may not add a rule, cite evidence nothing publishes, or carry a typo
//! that would be silently ignored. Every refusal names the rule and the key,
//! because a config file that fails quietly is worse than no config file at all.
//!
//! The compiled defaults stay the floor. With no file, [`Thresholds::default()`]
//! applies; this module only ever *overrides* what the code ships, and
//! `rules/*.toml` says the same numbers so that drift is a failing test rather
//! than a slow divergence.

use std::fmt;

use serde::Deserialize;

use crate::model::is_published_path;
use crate::rules::{RULES, Thresholds};

/// A percentage threshold has to fall inside this. Outside it the file is not
/// asking for a stricter rule, it is carrying a typo: `900` is not `90`, and the
/// un-overridden default would stay in place while the file looked applied.
const PERCENT: (f32, f32) = (1.0, 99.9);

/// A window a rule waits for, in minutes. A day is the longest any rule in the
/// catalogue needs, and a zero-minute window would be a rule that fires on one
/// sample while claiming to be sustained.
const WINDOW_MINUTES: (u64, u64) = (1, 24 * 60);

/// An uptime threshold, in minutes: a day to a year.
const UPTIME_MINUTES: (u64, u64) = (24 * 60, 365 * 24 * 60);

/// One rule's numbers, as the file wrote them. Every field is optional: a file
/// that names one threshold leaves the rest of that rule as the code has it.
#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(deny_unknown_fields)]
struct Entry {
    id: String,
    /// Restates the code. Checked, never applied: a file cannot make a warning
    /// into a critical.
    severity: Option<String>,
    confidence: Option<String>,
    requires: Option<Vec<String>>,
    warn_percent: Option<f32>,
    critical_percent: Option<f32>,
    sustained: Option<String>,
    long_after: Option<String>,
    /// The fixture that proves this rule fires, and the one that proves it does
    /// not fire when it should not. Named here so a rule cannot exist without
    /// them.
    firing: Option<String>,
    near_miss: Option<String>,
}

/// The document itself, so an unknown *top-level* key is refused too.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Document {
    #[serde(default)]
    rule: Vec<Entry>,
}

/// A parsed rules file. Nothing in it has been checked yet.
#[derive(Debug, Clone, PartialEq)]
pub struct RuleFile {
    rules: Vec<Entry>,
}

impl RuleFile {
    /// Parse the TOML.
    ///
    /// A structural problem — a key that does not exist, a value of the wrong
    /// type — is a [`Refusal`] like any other, so a caller handles one kind of
    /// error and the parser's line number survives in the message.
    pub fn parse(text: &str) -> Result<Self, Vec<Refusal>> {
        let document: Document = toml::from_str(text).map_err(|error| {
            vec![Refusal::Parse {
                message: error.to_string(),
            }]
        })?;

        let mut refusals = Vec::new();
        let mut seen: Vec<&str> = Vec::new();
        for entry in &document.rule {
            if seen.contains(&entry.id.as_str()) {
                refusals.push(Refusal::DuplicateRule {
                    id: entry.id.clone(),
                });
            } else {
                seen.push(entry.id.as_str());
            }
        }
        if refusals.is_empty() {
            Ok(Self {
                rules: document.rule,
            })
        } else {
            Err(refusals)
        }
    }

    /// The thresholds this file asks for, with the compiled defaults for every
    /// rule it does not mention.
    ///
    /// Everything that can be checked without the fixtures is checked here: the
    /// id exists in the compiled registry, the keys belong to that rule, every
    /// `requires` path is one [`crate::Snapshot::metrics`] publishes, and every
    /// number is inside the range the rule declares as possible.
    pub fn thresholds(&self) -> Result<Thresholds, Vec<Refusal>> {
        self.check(None)
    }

    /// The same, plus the fixture checks: every `firing` and `near_miss` names a
    /// scenario that exists.
    ///
    /// The fixtures are not compiled into the binary, so the running app cannot
    /// ask that half of the question — it can only refuse a scenario claimed
    /// twice. This is what the tests call, and what the app would call if the
    /// fixtures ever ship beside it.
    pub fn thresholds_with_scenarios(&self, scenarios: &[&str]) -> Result<Thresholds, Vec<Refusal>> {
        self.check(Some(scenarios))
    }

    /// The rule ids the file names, in file order, so the UI can say which
    /// numbers came from a file rather than from the build.
    pub fn rule_ids(&self) -> Vec<&str> {
        self.rules
            .iter()
            .map(|entry| entry.id.as_str())
            .collect()
    }

    fn check(&self, scenarios: Option<&[&str]>) -> Result<Thresholds, Vec<Refusal>> {
        let mut refusals = Vec::new();
        let mut limits = Thresholds::default();
        // One scenario proves one rule: a fixture claimed twice is a fixture
        // that will be read as evidence for whichever rule was edited last.
        let mut claims: Vec<(String, String)> = Vec::new();

        for entry in &self.rules {
            let Some(def) = RULES
                .iter()
                .map(|rule| rule.def)
                .find(|def| def.id == entry.id)
            else {
                refusals.push(Refusal::UnknownRule {
                    id: entry.id.clone(),
                });
                continue;
            };

            for (key, present) in [
                ("warn_percent", entry.warn_percent.is_some()),
                ("critical_percent", entry.critical_percent.is_some()),
                ("sustained", entry.sustained.is_some()),
                ("long_after", entry.long_after.is_some()),
            ] {
                if present && !allowed_keys(def.id).contains(&key) {
                    refusals.push(Refusal::NotThisRulesKey {
                        id: entry.id.clone(),
                        key,
                    });
                }
            }

            if let Some(word) = &entry.severity {
                if !def.severity.label().eq_ignore_ascii_case(word) {
                    refusals.push(Refusal::DisagreesWithCode {
                        id: entry.id.clone(),
                        field: "severity",
                    });
                }
            }
            if let Some(word) = &entry.confidence {
                if !def.confidence.label().eq_ignore_ascii_case(word) {
                    refusals.push(Refusal::DisagreesWithCode {
                        id: entry.id.clone(),
                        field: "confidence",
                    });
                }
            }
            if let Some(paths) = &entry.requires {
                for path in paths {
                    if !is_published_path(path) {
                        refusals.push(Refusal::UnpublishedPath {
                            id: entry.id.clone(),
                            path: path.clone(),
                        });
                    }
                }
                let same = paths.len() == def.requires.len()
                    && paths
                        .iter()
                        .zip(def.requires.iter())
                        .all(|(written, compiled)| written.as_str() == *compiled);
                if !same {
                    refusals.push(Refusal::DisagreesWithCode {
                        id: entry.id.clone(),
                        field: "requires",
                    });
                }
            }

            apply(&entry.id, entry, &mut limits, &mut refusals);

            for (field, name) in [
                ("firing", entry.firing.as_deref()),
                ("near_miss", entry.near_miss.as_deref()),
            ] {
                let Some(name) = name else { continue };
                if let Some(known) = scenarios {
                    if !known.contains(&name) {
                        refusals.push(Refusal::ScenarioNotKnown {
                            id: entry.id.clone(),
                            field,
                            name: name.to_owned(),
                        });
                    }
                }
                // Resolved to an owned value first: the borrow has to end before
                // the `None` arm can push, which is the one thing a match on
                // `find` cannot do in place.
                let claimed = claims
                    .iter()
                    .find(|(claimed, _)| claimed.as_str() == name)
                    .map(|(_, by)| by.clone());
                match claimed {
                    Some(by) => refusals.push(Refusal::ScenarioClaimedTwice {
                        name: name.to_owned(),
                        by,
                    }),
                    None => claims.push((name.to_owned(), entry.id.clone())),
                }
            }
        }

        if refusals.is_empty() {
            Ok(limits)
        } else {
            Err(refusals)
        }
    }
}

/// Which threshold keys a compiled rule answers to.
///
/// A key from another rule is refused rather than ignored: `critical_percent` on
/// `memory.pressure` would parse, do nothing, and leave the reader believing the
/// file had been applied.
fn allowed_keys(id: &str) -> &'static [&'static str] {
    match id {
        "disk.low_free_space" => &["warn_percent", "critical_percent", "sustained"],
        "memory.pressure" => &["warn_percent", "sustained"],
        "system.long_uptime" => &["long_after"],
        _ => &[],
    }
}

/// Apply one rule's numbers, refusing the ones that cannot be meant.
fn apply(id: &str, entry: &Entry, limits: &mut Thresholds, refusals: &mut Vec<Refusal>) {
    match id {
        "disk.low_free_space" => {
            let warn = percent(entry.warn_percent, id, "warn_percent", refusals);
            let critical = percent(entry.critical_percent, id, "critical_percent", refusals);
            let window = period(entry.sustained.as_deref(), id, "sustained", WINDOW_MINUTES, refusals);
            if let (Some(warn), Some(critical)) = (warn, critical) {
                if warn >= critical {
                    refusals.push(Refusal::InvertedRange {
                        id: "disk.low_free_space",
                        key: "critical_percent",
                    });
                }
            }
            if let Some(warn) = warn {
                limits.disk_warn_percent = warn;
            }
            if let Some(critical) = critical {
                limits.disk_critical_percent = critical;
            }
            if let Some(millis) = window {
                limits.disk_sustained_ms = millis;
            }
        }
        "memory.pressure" => {
            let warn = percent(entry.warn_percent, id, "warn_percent", refusals);
            let window = period(entry.sustained.as_deref(), id, "sustained", WINDOW_MINUTES, refusals);
            if let Some(warn) = warn {
                limits.memory_warn_percent = warn;
            }
            if let Some(millis) = window {
                limits.memory_sustained_ms = millis;
            }
        }
        "system.long_uptime" => {
            let window = period(entry.long_after.as_deref(), id, "long_after", UPTIME_MINUTES, refusals);
            if let Some(millis) = window {
                limits.uptime_long_seconds = millis / 1000;
            }
        }
        _ => {}
    }
}

/// A percentage, or the refusal that says why it cannot be one.
fn percent(value: Option<f32>, id: &str, key: &'static str, refusals: &mut Vec<Refusal>) -> Option<f32> {
    let value = value?;
    if (PERCENT.0..=PERCENT.1).contains(&value) {
        Some(value)
    } else {
        refusals.push(Refusal::OutOfRange {
            id: id.to_owned(),
            key,
            value: format!("{value}"),
            min: PERCENT.0,
            max: PERCENT.1,
        });
        None
    }
}

/// A duration in minutes, or the refusal that says why it cannot be one.
fn period(
    text: Option<&str>,
    id: &str,
    key: &'static str,
    bounds: (u64, u64),
    refusals: &mut Vec<Refusal>,
) -> Option<u64> {
    let text = text?;
    let Some(millis) = parse_duration(text) else {
        refusals.push(Refusal::BadDuration {
            id: id.to_owned(),
            key,
            value: text.to_owned(),
        });
        return None;
    };
    if (bounds.0 * 60_000..=bounds.1 * 60_000).contains(&millis) {
        Some(millis)
    } else {
        refusals.push(Refusal::OutOfWindow {
            id: id.to_owned(),
            key,
            value: text.to_owned(),
            min_minutes: bounds.0,
            max_minutes: bounds.1,
        });
        None
    }
}

/// `"10m"`, `"90s"`, `"2h"`, `"14d"` to milliseconds.
///
/// One number and one unit, no spaces and no plural: this is a thresholds file,
/// not a cron expression, and every unit a rule could need is here.
fn parse_duration(text: &str) -> Option<u64> {
    let mut chars = text.chars();
    let unit = chars.next_back()?;
    let number: u64 = chars.as_str().parse().ok()?;
    let millis = match unit {
        's' => 1_000,
        'm' => 60_000,
        'h' => 3_600_000,
        'd' => 86_400_000,
        _ => return None,
    };
    number.checked_mul(millis)
}

/// Why a file was refused. Every variant names the rule, and the key when there
/// is one, because "invalid config" is not something a user can act on.
#[derive(Debug, Clone, PartialEq)]
pub enum Refusal {
    /// The TOML did not parse. The message carries the parser's line and column.
    Parse { message: String },
    /// A rule id the compiled registry does not have.
    UnknownRule { id: String },
    /// The same rule named twice in one file.
    DuplicateRule { id: String },
    /// A threshold that belongs to a different rule.
    NotThisRulesKey { id: String, key: &'static str },
    /// A severity, confidence or `requires` that disagrees with the code.
    DisagreesWithCode { id: String, field: &'static str },
    /// A `requires` path that no snapshot publishes.
    UnpublishedPath { id: String, path: String },
    /// A percentage outside [`PERCENT`].
    OutOfRange {
        id: String,
        key: &'static str,
        value: String,
        min: f32,
        max: f32,
    },
    /// A duration outside the window the rule can mean.
    OutOfWindow {
        id: String,
        key: &'static str,
        value: String,
        min_minutes: u64,
        max_minutes: u64,
    },
    /// A warning threshold at or above the critical one.
    InvertedRange { id: &'static str, key: &'static str },
    /// A `firing` or `near_miss` naming a scenario that does not exist.
    ScenarioNotKnown {
        id: String,
        field: &'static str,
        name: String,
    },
    /// A scenario another rule already claims.
    ScenarioClaimedTwice { name: String, by: String },
}

impl fmt::Display for Refusal {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Parse { message } => write!(f, "the file does not parse: {message}"),
            Self::UnknownRule { id } => {
                write!(f, "`{id}` is not a rule this build has; a file cannot invent one")
            }
            Self::DuplicateRule { id } => {
                write!(f, "`{id}` appears twice, and only one of them can be meant")
            }
            Self::NotThisRulesKey { id, key } => {
                write!(f, "`{key}` is not a threshold of `{id}`, so it would be ignored")
            }
            Self::DisagreesWithCode { id, field } => write!(
                f,
                "`{id}` declares a different `{field}` than the compiled rule; only numbers may be \
                 overridden"
            ),
            Self::UnpublishedPath { id, path } => write!(
                f,
                "`{id}` requires `{path}`, which no snapshot publishes, so evidence could not cite it"
            ),
            Self::OutOfRange {
                id,
                key,
                value,
                min,
                max,
            } => write!(
                f,
                "`{id}` {key} = {value} is outside {min}..={max}; that is a typo, not a stricter rule"
            ),
            Self::OutOfWindow {
                id,
                key,
                value,
                min_minutes,
                max_minutes,
            } => write!(
                f,
                "`{id}` {key} = {value} is outside {min_minutes}m..={max_minutes}m"
            ),
            Self::InvertedRange { id, key } => write!(
                f,
                "`{id}` has `{key}` at or below its warning threshold, so critical never happens"
            ),
            Self::ScenarioNotKnown { id, field, name } => write!(
                f,
                "`{id}` names `{name}` as its {field}, and no fixture has that name"
            ),
            Self::ScenarioClaimedTwice { name, by } => write!(
                f,
                "`{name}` is already claimed by `{by}`; a fixture proves one rule"
            ),
        }
    }
}

impl std::error::Error for Refusal {}

#[cfg(test)]
mod tests {
    use super::*;

    const DISK: &str = include_str!("../rules/disk.toml");
    const MEMORY: &str = include_str!("../rules/memory.toml");
    const SYSTEM: &str = include_str!("../rules/system.toml");

    /// The scenario names the fixtures actually carry, read from the directory so
    /// a renamed fixture breaks this test instead of drifting past it.
    fn scenario_names() -> Vec<String> {
        let directory = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/scenarios");
        let mut names = Vec::new();
        for entry in std::fs::read_dir(&directory).expect("scenario directory") {
            let path = entry.expect("directory entry").path();
            if path.extension().and_then(|extension| extension.to_str()) != Some("json") {
                continue;
            }
            let text = std::fs::read_to_string(&path).expect("scenario file");
            let name = text
                .lines()
                .find_map(|line| line.trim().strip_prefix("\"name\": \""))
                .and_then(|rest| rest.strip_suffix("\","))
                .unwrap_or_else(|| panic!("no name in {}", path.display()));
            names.push(name.to_owned());
        }
        assert!(!names.is_empty(), "no fixtures found");
        names
    }

    fn known_scenarios() -> Vec<String> {
        scenario_names()
    }

    /// Every refusal a file produces, whichever stage produced it.
    fn refusals(text: &str) -> Vec<Refusal> {
        match RuleFile::parse(text) {
            Err(refusals) => refusals,
            Ok(file) => match file.thresholds() {
                Ok(_) => Vec::new(),
                Err(refusals) => refusals,
            },
        }
    }

    #[test]
    fn the_shipped_files_restate_the_compiled_numbers() {
        let names = known_scenarios();
        let known: Vec<&str> = names.iter().map(String::as_str).collect();
        for text in [DISK, MEMORY, SYSTEM] {
            let file = RuleFile::parse(text).expect("the shipped file parses");
            let limits = file
                .thresholds_with_scenarios(&known)
                .unwrap_or_else(|refusals| panic!("{refusals:?}"));
            // This is the proof that the front-end changes no verdict: the rules
            // are pure functions of (snapshot, store, thresholds), the thresholds
            // are equal, so every finding from every fixture is identical to the
            // one the compiled defaults produce.
            assert_eq!(limits, Thresholds::default(), "{text}");
            assert_eq!(file.rule_ids().len(), 1, "one rule per file: {text}");
        }
    }

    #[test]
    fn a_file_may_set_a_number() {
        let text = r#"
[[rule]]
id = "disk.low_free_space"
warn_percent = 80.0
sustained = "5m"
"#;
        let limits = RuleFile::parse(text)
            .expect("parses")
            .thresholds()
            .expect("is accepted");
        assert!((limits.disk_warn_percent - 80.0).abs() < f32::EPSILON);
        assert_eq!(limits.disk_sustained_ms, 5 * 60_000);
        // And nothing else moved.
        let memory = Thresholds::default().memory_warn_percent;
        assert!((limits.memory_warn_percent - memory).abs() < f32::EPSILON);
    }

    #[test]
    fn no_file_means_the_defaults() {
        let limits = RuleFile::parse("").expect("empty parses").thresholds().expect("no rules is fine");
        assert_eq!(limits, Thresholds::default());
    }

    #[test]
    fn a_rule_the_code_does_not_have_is_refused() {
        let text = "[[rule]]\nid = \"disk.almost_full\"\nwarn_percent = 90.0\n";
        assert!(refusals(text).contains(&Refusal::UnknownRule {
            id: "disk.almost_full".to_owned()
        }));
    }

    #[test]
    fn a_key_that_does_not_exist_is_refused() {
        let text = "[[rule]]\nid = \"disk.low_free_space\"\nwarn_pct = 90.0\n";
        let refused = refusals(text);
        assert!(matches!(refused.as_slice(), [Refusal::Parse { .. }]), "{refused:?}");
    }

    #[test]
    fn a_key_from_another_rule_is_refused() {
        let text = "[[rule]]\nid = \"memory.pressure\"\ncritical_percent = 97.0\n";
        assert!(refusals(text).contains(&Refusal::NotThisRulesKey {
            id: "memory.pressure".to_owned(),
            key: "critical_percent",
        }));
    }

    #[test]
    fn a_requires_path_nothing_publishes_is_refused() {
        let text = "[[rule]]\nid = \"memory.pressure\"\nrequires = [\"memory.commit_used\"]\n";
        assert!(refusals(text).contains(&Refusal::UnpublishedPath {
            id: "memory.pressure".to_owned(),
            path: "memory.commit_used".to_owned(),
        }));
    }

    #[test]
    fn a_percentage_that_is_a_typo_is_refused() {
        let text = "[[rule]]\nid = \"disk.low_free_space\"\nwarn_percent = 900.0\n";
        assert!(refusals(text).iter().any(|refusal| matches!(
            refusal,
            Refusal::OutOfRange { key: "warn_percent", .. }
        )));
    }

    #[test]
    fn a_warning_above_its_critical_is_refused() {
        let text = "[[rule]]\nid = \"disk.low_free_space\"\nwarn_percent = 98.0\ncritical_percent = 95.0\n";
        assert!(refusals(text).contains(&Refusal::InvertedRange {
            id: "disk.low_free_space",
            key: "critical_percent",
        }));
    }

    #[test]
    fn a_duration_that_is_not_one_is_refused() {
        for bad in ["10", "10 minutes", "ten m", "10M", "-5m"] {
            let text = format!("[[rule]]\nid = \"memory.pressure\"\nsustained = \"{bad}\"\n");
            assert!(
                matches!(refusals(&text).as_slice(), [Refusal::BadDuration { .. }]),
                "{bad} should be refused"
            );
        }
    }

    #[test]
    fn a_window_no_rule_could_mean_is_refused() {
        for bad in ["0m", "48h", "365d"] {
            let text = format!("[[rule]]\nid = \"memory.pressure\"\nsustained = \"{bad}\"\n");
            let refused = refusals(&text);
            assert!(
                refused.iter().any(|refusal| matches!(
                    refusal,
                    Refusal::OutOfWindow { .. } | Refusal::BadDuration { .. }
                )),
                "{bad} should be refused, got {refused:?}"
            );
        }
    }

    #[test]
    fn an_uptime_is_measured_in_days_not_minutes() {
        let text = "[[rule]]\nid = \"system.long_uptime\"\nlong_after = \"7d\"\n";
        let limits = RuleFile::parse(text).expect("parses").thresholds().expect("is accepted");
        assert_eq!(limits.uptime_long_seconds, 7 * 24 * 60 * 60);
    }

    #[test]
    fn a_severity_the_code_does_not_say_is_refused() {
        let text = "[[rule]]\nid = \"memory.pressure\"\nseverity = \"critical\"\n";
        assert!(refusals(text).contains(&Refusal::DisagreesWithCode {
            id: "memory.pressure".to_owned(),
            field: "severity",
        }));
    }

    #[test]
    fn restating_the_code_is_allowed() {
        let text = r#"
[[rule]]
id = "disk.low_free_space"
severity = "warning"
confidence = "certain"
requires = ["volume.*.percent_used"]
"#;
        assert!(RuleFile::parse(text).expect("parses").thresholds().is_ok());
    }

    #[test]
    fn a_scenario_no_fixture_has_is_refused() {
        let text = "[[rule]]\nid = \"disk.low_free_space\"\nfiring = \"disk-not-a-fixture\"\n";
        let names = known_scenarios();
        let known: Vec<&str> = names.iter().map(String::as_str).collect();
        let file = RuleFile::parse(text).expect("parses");
        assert!(matches!(
            file.thresholds_with_scenarios(&known),
            Err(ref refusals) if refusals.contains(&Refusal::ScenarioNotKnown {
                id: "disk.low_free_space".to_owned(),
                field: "firing",
                name: "disk-not-a-fixture".to_owned(),
            })
        ));
    }

    #[test]
    fn a_scenario_claimed_twice_is_refused() {
        let text = r#"
[[rule]]
id = "disk.low_free_space"
firing = "disk-full-for-eleven-minutes"

[[rule]]
id = "memory.pressure"
firing = "disk-full-for-eleven-minutes"
"#;
        assert!(refusals(text).contains(&Refusal::ScenarioClaimedTwice {
            name: "disk-full-for-eleven-minutes".to_owned(),
            by: "disk.low_free_space".to_owned(),
        }));
    }

    #[test]
    fn the_same_rule_twice_is_refused() {
        let text = "[[rule]]\nid = \"memory.pressure\"\n\n[[rule]]\nid = \"memory.pressure\"\n";
        assert!(refusals(text).contains(&Refusal::DuplicateRule {
            id: "memory.pressure".to_owned(),
        }));
    }

    #[test]
    fn a_key_nobody_knows_is_refused_even_at_the_top() {
        let refused = refusals("mood = \"hopeful\"\n");
        assert!(matches!(refused.as_slice(), [Refusal::Parse { .. }]), "{refused:?}");
    }

    #[test]
    fn every_refusal_names_what_it_refused() {
        // A refusal that says "invalid config" is a refusal a user cannot act on.
        let all = refusals("[[rule]]\nid = \"memory.pressure\"\ncritical_percent = 97.0\n");
        assert!(!all.is_empty());
        for refusal in all {
            let sentence = refusal.to_string();
            assert!(sentence.contains("memory.pressure"), "{sentence}");
        }
    }

    #[test]
    fn durations_parse_where_they_should() {
        assert_eq!(parse_duration("10m"), Some(10 * 60_000));
        assert_eq!(parse_duration("90s"), Some(90_000));
        assert_eq!(parse_duration("2h"), Some(7_200_000));
        assert_eq!(parse_duration("14d"), Some(14 * 86_400_000));
        assert_eq!(parse_duration("m"), None);
        assert_eq!(parse_duration("m10"), None);
        assert_eq!(parse_duration(""), None);
        // No panic on a multi-byte character where the unit should be.
        assert_eq!(parse_duration("10\u{00e9}"), None);
    }
}
