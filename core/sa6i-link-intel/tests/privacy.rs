// SPDX-License-Identifier: MPL-2.0
//! The promises about the intelligence core, checked against what it links.
//!
//! Three claims are made in writing and are easy to lose by accident:
//!
//! 1. **"Nothing leaves the machine."** Not "nothing is sent by the code we
//!    wrote" — nothing in the dependency graph is *able* to open a socket.
//! 2. **"`sa6i-link-intel` knows nothing about Windows, Qt or the link stack."**
//!    It is the bottom of the stack; the collectors and the shell sit above it.
//! 3. **"Diagnostics must not require a phone."** Which is the same claim seen
//!    from the other side: no dependency on `sa6i-link-core` or its protocol.
//!
//! Each is a property of the dependency graph, so it can be read out of
//! `Cargo.lock` instead of being asserted in a design document. A test is the
//! only version of this promise that survives a helpful future contributor.
//!
//! The graph is built by **name**, ignoring versions: the lock spells a version
//! only when a crate appears more than once, and a check that cannot name a
//! version has to keep every candidate edge rather than quietly drop one.

use std::{
    collections::{BTreeMap, BTreeSet, VecDeque},
    path::PathBuf,
};

/// Crates that can open a socket, or a TLS session, or both.
///
/// Deliberately not exhaustive of the ecosystem — it is a ratchet, not a proof
/// against every crate name that will ever exist. The point is that adding a
/// network stack to the core crate has to be a visible, deliberate edit to this
/// list as well.
const NETWORK_CAPABLE: &[&str] = &[
    "async-std",
    "curl",
    "curl-sys",
    "h2",
    "hyper",
    "hyper-util",
    "isahc",
    "mio",
    "native-tls",
    "openssl",
    "openssl-sys",
    "quinn",
    "quinn-proto",
    "reqwest",
    "rustls",
    "schannel",
    "socket2",
    "surf",
    "tokio",
    "tokio-tungstenite",
    "tungstenite",
    "ureq",
    "webpki",
    "webpki-roots",
];

/// Crates that must stay above `sa6i-link-intel` in the stack.
const NOT_BELOW_THE_SHELL: &[&str] = &[
    "sa6i-link-cli",
    "sa6i-link-core",
    "sa6i-link-ffi",
    "sa6i-link-intel-win",
    "sa6i-link-protocol",
    "winapi",
    "windows",
    "windows-sys",
];

fn lock_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../Cargo.lock")
}

/// The inside of a leading `"..."`, if the line starts with one.
fn quoted(line: &str) -> Option<String> {
    let rest = line.strip_prefix('"')?;
    let end = rest.find('"')?;
    Some(rest[..end].to_owned())
}

/// Store the block being read, if it has a name.
fn close_block(
    name: &mut Option<String>,
    dependencies: &mut Option<BTreeSet<String>>,
    graph: &mut BTreeMap<String, BTreeSet<String>>,
) {
    if let Some(name) = name.take() {
        let deps = dependencies.take().unwrap_or_default();
        graph.entry(name).or_default().extend(deps);
    }
}

/// `name -> its dependency names`, from a `Cargo.lock`.
fn dependency_graph(lock: &str) -> BTreeMap<String, BTreeSet<String>> {
    let mut graph: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut name: Option<String> = None;
    let mut dependencies: Option<BTreeSet<String>> = None;
    for raw in lock.lines() {
        let line = raw.trim();
        if line == "[[package]]" {
            close_block(&mut name, &mut dependencies, &mut graph);
            continue;
        }
        if dependencies.is_some() {
            if line == "]" {
                close_block(&mut name, &mut dependencies, &mut graph);
            } else if let Some(entry) = quoted(line) {
                if let Some(deps) = dependencies.as_mut() {
                    // `"serde 1.0.0"` and `"serde"` both mean the crate `serde`.
                    deps.insert(entry.split(' ').next().unwrap_or_default().to_owned());
                }
            }
            continue;
        }
        if let Some(rest) = line.strip_prefix("name = ") {
            name = quoted(rest);
        } else if let Some(rest) = line.strip_prefix("dependencies = [") {
            dependencies = Some(BTreeSet::new());
            if rest.trim() == "]" {
                close_block(&mut name, &mut dependencies, &mut graph);
            }
        }
    }
    close_block(&mut name, &mut dependencies, &mut graph);
    graph
}

/// Every crate reachable from `root`, excluding `root` itself.
fn closure_of(graph: &BTreeMap<String, BTreeSet<String>>, root: &str) -> BTreeSet<String> {
    let mut seen: BTreeSet<String> = BTreeSet::new();
    let mut queue: VecDeque<String> = VecDeque::new();
    queue.push_back(root.to_owned());
    while let Some(name) = queue.pop_front() {
        if !seen.insert(name.clone()) {
            continue;
        }
        if let Some(deps) = graph.get(&name) {
            for dep in deps {
                if !seen.contains(dep) {
                    queue.push_back(dep.clone());
                }
            }
        }
    }
    seen.remove(root);
    seen
}

#[test]
fn the_lock_parser_reads_names_and_dependency_lists() {
    // A miniature lock in the real format, including a versioned edge: if the
    // parser ever stops understanding that shape, this fails before the privacy
    // check does, and for a reason a person can read.
    let lock = "\
[[package]]
name = \"root\"
version = \"0.1.0\"
dependencies = [
 \"direct\",
 \"versioned 2.0.0\",
]

[[package]]
name = \"direct\"
version = \"1.0.0\"

[[package]]
name = \"versioned\"
version = \"2.0.0\"
dependencies = [
 \"deep\",
]

[[package]]
name = \"deep\"
version = \"3.0.0\"
";
    let graph = dependency_graph(lock);
    assert_eq!(graph["root"], BTreeSet::from(["direct".to_owned(), "versioned".to_owned()]));
    assert_eq!(graph["versioned"], BTreeSet::from(["deep".to_owned()]));
    assert!(graph["deep"].is_empty());
    assert_eq!(
        closure_of(&graph, "root"),
        BTreeSet::from(["deep".to_owned(), "direct".to_owned(), "versioned".to_owned()])
    );
}

#[test]
fn neither_intel_crate_can_open_a_socket() {
    let path = lock_path();
    let Ok(lock) = std::fs::read_to_string(&path) else {
        panic!("cannot read {} — this check must not be skipped", path.display());
    };
    let graph = dependency_graph(&lock);
    assert!(graph.len() > 100, "the lock parsed into only {} packages", graph.len());
    // Both intel crates: the collectors are as forbidden a network as the core.
    for root in ["sa6i-link-intel", "sa6i-link-intel-win"] {
        let closure = closure_of(&graph, root);
        // A vacuous pass is the failure mode of a test like this, so the pieces
        // that must be in the graph are checked first.
        for expected in ["serde", "tracing"] {
            assert!(closure.contains(expected), "{root}: {expected} is missing from the closure");
        }
        let offenders: Vec<&str> =
            NETWORK_CAPABLE.iter().copied().filter(|name| closure.contains(*name)).collect();
        assert!(
            offenders.is_empty(),
            "{root} must not be linked to anything that can open a socket, found: {offenders:?}"
        );
    }
}

#[test]
fn the_core_crate_is_below_the_shell_and_the_link_stack() {
    let path = lock_path();
    let lock = std::fs::read_to_string(&path).expect("the workspace lock");
    let closure = closure_of(&dependency_graph(&lock), "sa6i-link-intel");
    let offenders: Vec<&str> =
        NOT_BELOW_THE_SHELL.iter().copied().filter(|name| closure.contains(*name)).collect();
    assert!(
        offenders.is_empty(),
        "sa6i-link-intel is the bottom of the stack, but these are below it too: {offenders:?}"
    );
}
