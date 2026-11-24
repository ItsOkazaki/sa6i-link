// SPDX-License-Identifier: MPL-2.0
//! Golden scenarios: a machine behaviour written down, and the findings it must
//! produce.
//!
//! Every file in `tests/scenarios/` is both the input and the expected answer,
//! so a reviewer reads one file and sees the claim and the result together. The
//! files are recipes, not 600 hand-written snapshots: a segment says "ten
//! minutes at 95 % full" and the harness expands it to a 1 Hz sample series,
//! which is what the collector would have produced.
//!
//! Two properties are enforced here rather than hoped for:
//!
//! - **A finding appears exactly when the evidence says it should** — not one
//!   scenario more, not one fewer. Both the firing case and the near-miss are
//!   written down, because a rule nobody can make silent is a rule that pages
//!   people for nothing.
//! - **Every rule ships both.** `every_rule_has_a_firing_case_and_a_near_miss`
//!   fails if a rule in `RULES` has no scenario proving it fires and none
//!   proving it stays quiet, so adding a rule without fixtures breaks the build
//!   instead of shipping a guess.

use std::{collections::BTreeSet, fs, path::PathBuf};

use sa6i_link_intel::{
    Bytes, CpuSample, DiskIoSample, Finding, GpuAdapter, GpuSample, MemorySample, MetricState, ProcessSample,
    RULES, SampleStore, Severity, Snapshot, Timestamp, VolumeKind, VolumeSample, WhyUnknown, evaluate,
};

/// A fixed wall-clock base so the fixtures are deterministic: 2023-11-14T22:13:20Z.
const BASE_TIME: i64 = 1_700_000_000_000;

const MIB: u64 = 1024 * 1024;
/// 16 GiB of physical memory, the machine these numbers describe.
const MEMORY_TOTAL: u64 = 16 * 1024 * MIB;
/// A 500 GiB data volume.
const VOLUME_TOTAL: u64 = 500 * 1024 * MIB;
/// The commit limit the commit fixtures describe: 16 GiB of RAM and an 8 GiB
/// pagefile, which is what a default Windows install of this size would have.
const COMMIT_LIMIT: u64 = 24 * 1024 * MIB;

#[derive(Debug, serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct Scenario {
    /// Stable id, used in the failure message.
    name: String,
    /// One sentence a non-engineer can check the numbers against.
    about: String,
    segments: Vec<Segment>,
    /// Findings that must appear.
    #[serde(default)]
    expect: Vec<Expected>,
    /// Findings that must *not* appear, even though the scenario provokes them.
    #[serde(default)]
    quiets: Vec<String>,
}

/// A stretch of time during which the machine behaves the same way.
#[derive(Debug, serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct Segment {
    minutes: u32,
    #[serde(default = "default_cpu")]
    cpu_percent: f32,
    #[serde(default = "default_memory")]
    memory_percent: f32,
    /// Commit charge as a share of the commit limit. Absent means the machine
    /// would not say, which is how most machines are described here: a rule that
    /// needs it has to keep quiet rather than assume.
    #[serde(default)]
    commit_percent: Option<f32>,
    #[serde(default)]
    volumes: Vec<VolumeSpec>,
    /// Graphics adapters, when the scenario is about VRAM. Absent means the
    /// machine has no GPU counters — every Windows 8.1 and older box — and is
    /// not the same thing as an adapter using no memory.
    #[serde(default)]
    gpus: Vec<GpuSpec>,
    #[serde(default = "default_uptime")]
    uptime_days: f64,
    /// Average seconds per disk transfer during this segment. Absent means the
    /// scenario's machine cannot read the counter, which is what an old Windows
    /// or a disabled PDH looks like.
    #[serde(default)]
    disk_seconds_per_transfer: Option<f32>,
    /// Hard faults per second resolved from disk, from `Pages Input/sec`. Absent
    /// means the scenario's machine cannot read the counter.
    #[serde(default)]
    pages_input_per_second: Option<f32>,
    /// The processes on the machine during this segment. Absent means the
    /// scenario does not describe them, which keeps every older fixture honest.
    #[serde(default)]
    processes: Vec<ProcessSpec>,
    /// Percent busy for each logical processor, in index order. Absent means the
    /// scenario does not describe the machine's cores, so a rule about cores has
    /// nothing to read there rather than reading a blank as "all idle".
    #[serde(default)]
    cores: Vec<f32>,
}

/// One process during one segment.
#[derive(Debug, serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct ProcessSpec {
    pid: u32,
    #[serde(default)]
    name: String,
    /// Percent of one core, as Task Manager reports it: above 100 is possible and
    /// is not an error.
    cpu_percent: f32,
    #[serde(default = "default_working_set")]
    working_set_mb: u64,
    /// The creation stamp. Two segments with the same pid and different stamps
    /// describe two processes, which is what Windows does with a reused pid.
    #[serde(default)]
    created: u64,
}

fn default_working_set() -> u64 {
    100
}

#[derive(Debug, serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct GpuSpec {
    /// The counter instance name, e.g. `luid_0x00000000_0x0000FB33_phys_0`.
    instance: String,
    /// MiB in use. Absent means the counter gave no number.
    #[serde(default)]
    used_mb: Option<u64>,
    /// MiB the adapter owns. `Some(0)` is an integrated GPU and is a fact;
    /// absent means the counter refused.
    #[serde(default)]
    limit_mb: Option<u64>,
}

#[derive(Debug, serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct VolumeSpec {
    letter: String,
    /// `fixed`, `removable`, `network`, `optical`, `ram` or `unknown`.
    #[serde(default = "default_kind")]
    kind: String,
    /// `null` means the read failed, which the model must keep as "unknown".
    percent_used: Option<f32>,
}

#[derive(Debug, serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct Expected {
    rule: String,
    /// The severity label, spelled as the UI spells it.
    severity: String,
    subject: String,
}

fn default_cpu() -> f32 {
    20.0
}

fn default_memory() -> f32 {
    50.0
}

fn default_uptime() -> f64 {
    2.0
}

fn default_kind() -> String {
    "fixed".to_owned()
}

fn scenario_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/scenarios")
}

/// Every scenario file, sorted by name so a failure is reproducible.
fn load_scenarios() -> Vec<Scenario> {
    let dir = scenario_dir();
    let mut paths: Vec<PathBuf> = fs::read_dir(&dir)
        .unwrap_or_else(|error| panic!("can't read {}: {error}", dir.display()))
        .map(|entry| entry.expect("a readable directory entry").path())
        .filter(|path| path.extension().is_some_and(|ext| ext == "json"))
        .collect();
    paths.sort();
    assert!(!paths.is_empty(), "no scenarios in {}", dir.display());
    paths
        .iter()
        .map(|path| {
            let text = fs::read_to_string(path)
                .unwrap_or_else(|error| panic!("can't read {}: {error}", path.display()));
            serde_json::from_str(&text)
                .unwrap_or_else(|error| panic!("{} is not a valid scenario: {error}", path.display()))
        })
        .collect()
}

/// The 1 Hz sample series the collector would have produced for this scenario.
///
/// A segment of `n` minutes contributes `60n` samples, and one closing sample
/// is added so that the series spans exactly the minutes it claims: a ten-minute
/// window needs a sample at each end of it.
fn samples_of(scenario: &Scenario) -> Vec<Snapshot> {
    let mut samples = Vec::new();
    let mut index = 0u64;
    for segment in &scenario.segments {
        for _ in 0..u64::from(segment.minutes) * 60 {
            samples.push(snapshot(index, segment));
            index += 1;
        }
    }
    let last = scenario.segments.last().expect("a scenario has at least one segment");
    samples.push(snapshot(index, last));
    samples
}

fn snapshot(index: u64, segment: &Segment) -> Snapshot {
    Snapshot {
        seq: index + 1,
        taken_at: Timestamp(BASE_TIME + (index as i64) * 1000),
        monotonic_ms: index * 1000,
        cpu: CpuSample {
            percent: MetricState::Value(segment.cpu_percent),
            // A segment that describes its cores gives one reading each; one that
            // does not leaves the list empty, which is what a machine whose
            // per-core counters failed looks like.
            per_core: segment.cores.iter().map(|percent| MetricState::Value(*percent)).collect(),
        },
        memory: memory(segment),
        volumes: segment.volumes.iter().map(volume).collect(),
        disk_io: match segment.disk_seconds_per_transfer {
            Some(seconds) => DiskIoSample {
                // The fixtures do not invent throughput: a scenario that describes
                // a slow disk describes a slow disk and nothing else.
                read_bytes_per_second: MetricState::Unknown(WhyUnknown::NotCollectedYet),
                write_bytes_per_second: MetricState::Unknown(WhyUnknown::NotCollectedYet),
                avg_seconds_per_transfer: MetricState::Value(seconds),
            },
            None => DiskIoSample::unavailable(WhyUnknown::NotCollectedYet),
        },
        gpu: gpu(segment),
        processes: segment.processes.iter().map(process).collect(),
        uptime: MetricState::Value((segment.uptime_days * 86_400.0) as u64),
    }
}

/// The graphics adapters a segment describes.
///
/// A scenario without a `gpus` list is a machine whose GPU counters nobody read,
/// which is what every Windows 8.1 and older machine is — not a machine with no
/// graphics card.
fn gpu(segment: &Segment) -> MetricState<GpuSample> {
    if segment.gpus.is_empty() {
        return MetricState::Unknown(WhyUnknown::NotCollectedYet);
    }
    MetricState::Value(GpuSample {
        adapters: segment
            .gpus
            .iter()
            .map(|spec| GpuAdapter {
                instance: spec.instance.clone(),
                dedicated_used: match spec.used_mb {
                    Some(mb) => MetricState::Value(Bytes(mb * MIB)),
                    None => MetricState::Unknown(WhyUnknown::NotCollectedYet),
                },
                dedicated_limit: match spec.limit_mb {
                    Some(mb) => MetricState::Value(Bytes(mb * MIB)),
                    None => MetricState::Unknown(WhyUnknown::NotCollectedYet),
                },
            })
            .collect(),
    })
}

fn memory(segment: &Segment) -> MemorySample {
    let percent_used = segment.memory_percent;
    let free = (MEMORY_TOTAL as f64 * f64::from(100.0 - percent_used) / 100.0) as u64;
    let (commit_used, commit_limit) = match segment.commit_percent {
        Some(percent) => (
            MetricState::Value(Bytes((COMMIT_LIMIT as f64 * f64::from(percent) / 100.0) as u64)),
            MetricState::Value(Bytes(COMMIT_LIMIT)),
        ),
        None => (
            MetricState::Unknown(WhyUnknown::NotCollectedYet),
            MetricState::Unknown(WhyUnknown::NotCollectedYet),
        ),
    };
    MemorySample {
        total: MetricState::Value(Bytes(MEMORY_TOTAL)),
        available: MetricState::Value(Bytes(free)),
        commit_limit,
        commit_used,
        pages_input_per_second: match segment.pages_input_per_second {
            Some(pages) => MetricState::Value(pages),
            None => MetricState::Unknown(WhyUnknown::NotCollectedYet),
        },
    }
}

fn process(spec: &ProcessSpec) -> ProcessSample {
    ProcessSample {
        pid: spec.pid,
        name: if spec.name.is_empty() { format!("proc{}.exe", spec.pid) } else { spec.name.clone() },
        working_set: MetricState::Value(Bytes(spec.working_set_mb * MIB)),
        cpu_percent: MetricState::Value(spec.cpu_percent),
        created: MetricState::Value(spec.created),
    }
}

fn volume(spec: &VolumeSpec) -> VolumeSample {
    let kind = match spec.kind.as_str() {
        "removable" => VolumeKind::Removable,
        "network" => VolumeKind::Network,
        "optical" => VolumeKind::Optical,
        "ram" => VolumeKind::Ram,
        "unknown" => VolumeKind::Unknown,
        _ => VolumeKind::Fixed,
    };
    let (total, free) = match spec.percent_used {
        Some(percent) => {
            let free = (VOLUME_TOTAL as f64 * f64::from(100.0 - percent) / 100.0) as u64;
            (MetricState::Value(Bytes(VOLUME_TOTAL)), MetricState::Value(Bytes(free)))
        }
        // A volume Windows would not answer for is unknown, never 0 % used.
        None => (
            MetricState::Unknown(WhyUnknown::CollectorFailed),
            MetricState::Unknown(WhyUnknown::CollectorFailed),
        ),
    };
    VolumeSample { mount: format!("{}\\", spec.letter), kind, total, free }
}

fn triple(rule: &str, severity: &str, subject: &str) -> (String, String, String) {
    (rule.to_owned(), severity.to_owned(), subject.to_owned())
}

fn actual(findings: &[Finding]) -> BTreeSet<(String, String, String)> {
    findings.iter().map(|finding| triple(&finding.rule, finding.severity.label(), &finding.subject)).collect()
}

fn expected(scenario: &Scenario) -> BTreeSet<(String, String, String)> {
    scenario.expect.iter().map(|want| triple(&want.rule, &want.severity, &want.subject)).collect()
}

#[test]
fn every_scenario_produces_exactly_the_findings_it_promises() {
    let scenarios = load_scenarios();
    for scenario in &scenarios {
        let mut store = SampleStore::with_capacity(4096);
        for sample in samples_of(scenario) {
            store.push(sample);
        }
        let latest = store.latest().expect("a scenario has samples").clone();
        let findings = evaluate(&latest, &store);
        assert_eq!(actual(&findings), expected(scenario), "{} — {}", scenario.name, scenario.about);
        for finding in &findings {
            assert!(
                !finding.evidence.is_empty(),
                "{}: {} was shown without evidence",
                scenario.name,
                finding.rule
            );
        }
        for quiet in &scenario.quiets {
            assert!(
                !findings.iter().any(|finding| finding.rule == *quiet),
                "{}: {quiet} was supposed to stay quiet — {}",
                scenario.name,
                scenario.about
            );
        }
    }
    assert!(scenarios.len() >= 8, "expected at least 8 scenarios, found {}", scenarios.len());
}

#[test]
fn every_rule_has_a_firing_case_and_a_near_miss() {
    let scenarios = load_scenarios();
    for rule in RULES {
        let fires =
            scenarios.iter().any(|scenario| scenario.expect.iter().any(|want| want.rule == rule.def.id));
        let quiet = scenarios.iter().any(|scenario| scenario.quiets.iter().any(|id| id == rule.def.id));
        assert!(fires, "no scenario proves that {} fires", rule.def.id);
        assert!(quiet, "no scenario proves that {} can stay quiet", rule.def.id);
    }
}

#[test]
fn the_json_a_page_receives_has_the_field_names_it_expects() {
    // The Monitor page and the CLI read this shape; renaming a field is a
    // breaking change even though nothing fails to compile.
    let segment = Segment {
        minutes: 1,
        cpu_percent: 42.0,
        memory_percent: 50.0,
        commit_percent: None,
        volumes: vec![VolumeSpec {
            letter: "C:".to_owned(),
            kind: "fixed".to_owned(),
            percent_used: Some(30.0),
        }],
        uptime_days: 1.0,
        processes: Vec::new(),
        disk_seconds_per_transfer: None,
        pages_input_per_second: None,
        cores: Vec::new(),
        gpus: Vec::new(),
    };
    let json = serde_json::to_value(snapshot(0, &segment)).expect("a snapshot is serialisable");
    assert_eq!(
        names(&json),
        [
            "cpu",
            "disk_io",
            "gpu",
            "memory",
            "monotonic_ms",
            "processes",
            "seq",
            "taken_at",
            "uptime",
            "volumes"
        ]
    );
    // `per_core` and `pages_input_per_second` are always present, even when they
    // are empty and `unknown`: a page that has to guess whether a key is there is
    // a page that will one day draw a missing number as zero.
    assert_eq!(names(&json["cpu"]), ["per_core", "percent"]);
    assert_eq!(
        names(&json["memory"]),
        ["available", "commit_limit", "commit_used", "pages_input_per_second", "total"]
    );
    assert_eq!(names(&json["volumes"][0]), ["free", "kind", "mount", "total"]);
    // A measurement that is missing keeps its reason in the JSON, so no page
    // can quietly render it as 0.
    let expected = serde_json::json!({ "state": "unknown", "value": "not_collected_yet" });
    assert_eq!(json["memory"]["commit_used"], expected);
}

/// The keys of a JSON object, sorted, because that is the order JSON maps give.
fn names(value: &serde_json::Value) -> Vec<String> {
    let mut keys: Vec<String> = value
        .as_object()
        .unwrap_or_else(|| panic!("expected an object, got {value}"))
        .keys()
        .cloned()
        .collect();
    keys.sort();
    keys
}

#[test]
fn a_severity_word_is_never_invented_by_a_scenario() {
    // The fixture spells severities the way the UI does; a typo in a fixture
    // would otherwise silently make an expectation unreachable.
    let labels: BTreeSet<&str> = [Severity::Info, Severity::Notice, Severity::Warning, Severity::Critical]
        .into_iter()
        .map(Severity::label)
        .collect();
    for scenario in load_scenarios() {
        for want in &scenario.expect {
            assert!(
                labels.contains(want.severity.as_str()),
                "{}: \"{}\" is not a severity label",
                scenario.name,
                want.severity
            );
        }
    }
}
