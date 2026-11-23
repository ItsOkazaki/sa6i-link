// SPDX-License-Identifier: GPL-3.0-or-later
//! `IntelHost`: the Monitor page's sampler.
//!
//! One thread samples the machine, evaluates the rules and hands the page a
//! finished frame once a second. Everything with an opinion — which number is
//! big, what a missing reading says, where the line has holes — happens in
//! `sa6i_link_intel::view`, which is tested. This file owns the thread, the
//! ring of samples the rules need, and nothing else.
//!
//! The frame crosses to QML as JSON: `MonitorView` is the wire format, and one
//! `QString` property means one binding to re-evaluate rather than a dozen.

use std::{
    pin::Pin,
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
};

use cxx_qt::{CxxQtType, Threading};
use cxx_qt_lib::QString;

use sa6i_link_intel::{Collector, SampleStore, evaluate, monitor_view};

/// Sampling rate. One second is what Task Manager shows and what the plan
/// budgets for thirty minutes.
const INTERVAL_MS: u32 = 1_000;

#[cxx_qt::bridge]
pub mod qobject {
    unsafe extern "C++" {
        include!("cxx-qt-lib/qstring.h");
        type QString = cxx_qt_lib::QString;
    }

    #[auto_cxx_name]
    unsafe extern "RustQt" {
        #[qobject]
        #[qml_element]
        #[qml_singleton]
        /// The newest frame, as JSON (`sa6i_link_intel::MonitorView`), or empty
        /// before the first sample.
        #[qproperty(QString, frame)]
        /// Whether the sampler thread is running.
        #[qproperty(bool, live)]
        /// Samples taken since starting: the page says "live" only when this
        /// is moving.
        #[qproperty(i32, samples)]
        /// Milliseconds between samples.
        #[qproperty(i32, interval_ms)]
        type IntelHost = super::IntelHostRust;
    }

    unsafe extern "RustQt" {
        /// Starts sampling. Calling it while running does nothing.
        #[qinvokable]
        fn start(self: Pin<&mut IntelHost>);
        /// Stops sampling, keeping the last frame on screen.
        #[qinvokable]
        fn stop(self: Pin<&mut IntelHost>);
    }

    impl cxx_qt::Threading for IntelHost {}
    impl cxx_qt::Initialize for IntelHost {}
}

#[derive(Debug)]
pub struct IntelHostRust {
    frame: QString,
    live: bool,
    samples: i32,
    interval_ms: i32,
    /// Belongs to the thread that is running: cleared by `stop`, replaced by
    /// `start` so a thread still winding down cannot be revived.
    running: Arc<AtomicBool>,
}

impl Default for IntelHostRust {
    fn default() -> Self {
        Self {
            frame: QString::from(""),
            live: false,
            samples: 0,
            interval_ms: INTERVAL_MS as i32,
            running: Arc::new(AtomicBool::new(false)),
        }
    }
}

impl qobject::IntelHost {
    fn start(mut self: Pin<&mut Self>) {
        if self.rust().live {
            return;
        }
        // A flag of its own for this run: a thread still winding down keeps the
        // old one, which is already false, so a quick stop and start cannot
        // leave two samplers writing frames.
        let running = Arc::new(AtomicBool::new(true));
        self.as_mut().rust_mut().running = running.clone();
        self.as_mut().set_live(true);
        let qt = self.qt_thread();
        let spawned = std::thread::Builder::new()
            .name("sa6i-intel".to_owned())
            .spawn(move || sampler(running, qt));
        if spawned.is_err() {
            // No thread means no Monitor; say so rather than showing a page
            // that will never move.
            tracing::error!("the Monitor's sampler thread did not start");
            self.as_mut().set_live(false);
        }
    }

    fn stop(mut self: Pin<&mut Self>) {
        let stopped = Arc::new(AtomicBool::new(false));
        let previous = {
            let this = self.as_mut().rust_mut();
            std::mem::replace(&mut this.running, stopped)
        };
        previous.store(false, Ordering::Release);
        self.as_mut().set_live(false);
    }
}

/// The sampling loop. Owns the collector, because the Windows handles inside it
/// belong to the thread that opened them, and the store, because a rule's
/// window is minutes long while a frame is one second.
fn sampler(running: Arc<AtomicBool>, qt: cxx_qt::CxxQtThread<qobject::IntelHost>) {
    let mut collector = sa6i_link_intel_win::WindowsCollector::new();
    let mut store = SampleStore::default();
    let mut recent: Vec<sa6i_link_intel::Snapshot> = Vec::new();
    let mut seq = 0u64;
    let started = std::time::Instant::now();
    while running.load(Ordering::Acquire) {
        seq += 1;
        let snapshot = collector.sample(seq, started.elapsed().as_millis() as u64);
        store.push(snapshot.clone());
        recent.push(snapshot.clone());
        if recent.len() > sa6i_link_intel::SPARKLINE_POINTS {
            recent.remove(0);
        }
        let findings = evaluate(&snapshot, &store);
        let view = monitor_view(&snapshot, &recent, findings.len());
        let Ok(json) = serde_json::to_string(&view) else {
            // A frame that cannot be serialized is a bug in the view, not a
            // measurement problem: stop rather than show a frozen page.
            tracing::error!("monitor frame did not serialize");
            break;
        };
        if qt
            .queue(move |mut object| {
                object.as_mut().set_frame(QString::from(&json));
                // Read as a field, like every other bridge in this app: the
                // generated type derefs to the Rust struct that holds it.
                let samples = object.samples.saturating_add(1);
                object.as_mut().set_samples(samples);
            })
            .is_err()
        {
            // The page went away.
            break;
        }
        // Sleep in slices so `stop()` is felt within ~50 ms, not a second.
        let deadline = std::time::Instant::now() + std::time::Duration::from_millis(INTERVAL_MS.into());
        while std::time::Instant::now() < deadline && running.load(Ordering::Acquire) {
            std::thread::sleep(std::time::Duration::from_millis(50));
        }
    }
    let _ = qt.queue(|mut object| object.as_mut().set_live(false));
}
