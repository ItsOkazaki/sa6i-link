# Sa6i Link and Sa6i Clean — presentation pack and judge Q&A

This is one document that holds every format you might be asked for: a 30-second
answer, a 5-minute stage pitch, a 12-minute technical talk, a poster, a live demo
script, a video shot list, a written abstract — and the questions a judge can ask
afterwards, with answers that survive being asked twice.

Everything in it is drawn from this repository, and the last two sections exist to
keep you out of the one trap that costs more than a weak demo: claiming something
the code cannot back up.

> **Read this first.** The project has a genuinely unusual selling point for a
> competition, and it is not the feature list. It is that the repository records,
> in writing, the difference between what is measured and what is believed. Present
> that as the product and you will sound like engineers. Present the feature list
> instead and you will sound like every other deck in the room.

---

## 0. How to use this pack

| The situation | Read |
| --- | --- |
| Someone asks "what is it?" in a corridor | §2.1 — 30 seconds |
| You get the floor for two minutes | §2.2 — 60-second pitch, then stop |
| Stage, short slot | §2.3 — 8 slides, 5 minutes |
| Stage, long slot / technical track | §2.4 — 12–15 minutes |
| Poster session | §3.2 |
| They say "show me" | §3.3 — the 4-minute demo, with fallbacks |
| They ask for a submission or a video | §3.4, §3.5 |
| The questions start | §6 — grouped, short, with *if pushed* lines |
| You have five minutes before going on | §8 — the cheat sheet |

---

## 1. The one-screen answer

### 1.1 The two sentences

> **Sa6i Link** connects an Android phone to a Windows PC — notifications, SMS and
> calls, clipboard, files, screen mirroring, camera — and it diagnoses the PC
> itself: it measures the machine, and every conclusion it draws arrives with the
> measurement that produced it.
>
> **Sa6i Clean** is a cleaner we did not write. We took the published Cleanly 0.2.0
> build, proved byte-for-byte that its packaged JavaScript is that project's source
> plus our documented patches, closed a deletion path that could follow a redirected
> folder, and hosted it inside Sa6i Link's own window.

### 1.2 Why that pairing is the point, not a coincidence

Both halves are the same sentence said twice: *a tool may only say what it can
show you.*

- The diagnosis half refuses to render an unreadable measurement as `0`. A missing
  number carries the reason it is missing, and the page says so instead of drawing
  a flat line at the bottom.
- The cleaning half refuses to delete through a link it has not checked, and the
  release notes say plainly that **no cleanup has ever been run** — because the
  machine that would prove it is the machine we cannot risk.

That is an unusual thing to be able to say in front of judges, and it is the
whole reason the project is worth five minutes of their attention.

### 1.3 The product's own modalities — how a person actually uses it

If the question is about input and output channels rather than presentation
formats, this is the answer:

| Modality | Where it lives |
| --- | --- |
| Touch and typing on the phone | Android app, Kotlin Compose |
| Keyboard and mouse on the PC | Qt Quick desktop app, 13 pages |
| Voice | voice typing in the Deck; the phone dictating into the PC |
| Motion | air mouse / remote input from the phone |
| Screen as a channel | phone screen mirrored to the window; phone as a webcam on Windows 11 |
| Ambient surfaces | Island, Shelf, Command Palette, Timeline, Handoff |
| Machine state as a channel | the Monitor page: CPU, memory, disks, GPU, processes, and the rules over them |

### 1.4 Status, one line each — say this before anyone asks

| | State | The honest clause |
| --- | --- | --- |
| Link (phone ↔ PC) | **working** | the genuine asset: transport, capability matrix, transfer, mirroring — though the Windows package people download is a patched build, not a source build |
| Intel (measure + diagnose) | **built, not yet validated on hardware** | written, simulated against 28 fixtures, never compared with Task Manager |
| Clean | **hardened candidate** | runs in the user's window on Windows 7 + VxKex; no cleanup has ever been executed |
| Assistant (local model) | **not built** | designed as an optional leaf so the product is complete without it |

---

## 2. The pitches

### 2.1 Thirty seconds, verbatim

> "I built a tool that connects an Android phone to a PC, and then turns around and
> tells you the truth about the PC. Sa6i Link moves files, mirrors the screen, brings
> your notifications and clipboard across — and on the same machine it measures CPU,
> memory, disk and GPU, and explains every problem with the evidence that proves it.
> The second half of the demo is a cleaner we didn't write: we proved what was inside
> it, fixed a deletion path that could follow a redirected folder, and put it in the
> same window. Everything runs on the two devices. Nothing is sent anywhere."

Then stop. Do not fill the silence.

### 2.2 Sixty seconds

> "Two devices, two directions.
>
> The phone is the device people actually carry; the PC is the device they actually
> work on. Sa6i Link joins them — notifications you can reply to, SMS and calls,
> shared clipboard, file transfer that resumes, screen mirroring with control, the
> phone as a webcam. That half is built, and it runs on a real phone and a real PC.
>
> The other direction is the diagnosis. The PC measures itself: CPU, memory
> including commit charge and paging, every volume, disk latency, GPU, the heaviest
> processes. Ten rules run over those numbers, and a finding is only allowed to exist
> if it carries the measurement behind it — no evidence, no finding. A measurement
> that failed is not a zero; it says *why* it failed, on screen.
>
> And the cleaner. We didn't write it — it is the published Cleanly build — so the
> first thing we did was prove what is inside it: its JavaScript matches that
> project's source byte for byte, plus the patches we list. Then we found a real
> deletion path: a folder redirected by a junction above a cache root. We closed it,
> and we wrote down that we have never run a cleanup, because we can't risk the only
> machine we have.
>
> Nothing leaves the two devices. That is enforced by a test that reads the
> dependency graph, not by a promise on a slide."

If you are speaking Arabic, this is the same sixty seconds:

> «ساقي لينك يربط هاتف أندرويد بحاسوب ويندوز: إشعارات ورسائل ومكالمات، حافظة مشتركة،
> نقل ملفات، وبثّ الشاشة. وفي الاتجاه المقابل، يشخّص الحاسوب نفسه: يقيس المعالج
> والذاكرة والقرص، وكل نتيجة يقدّمها تأتي مع القياس الذي أنتجها. وأما ساقي كلين فهو
> منظّف لم نكتبه: أثبتنا – بملفّاته كلّها – أنه البناء المنشور نفسه، وأغلقنا طريق حذف
> كان يمكن أن يتبع مجلّداً مُعاد توجيهه، ثم أدرجناه في النافذة نفسها. كل شيء يبقى على
> الجهازين — لا سحابة ولا قياس عن بُعد — وهذا مُثبت باختبار يقرأ شجرة الاعتماديات،
> لا بوعد في عرض تقديمي.»

French, if the panel is francophone:

> « Sa6i Link relie un téléphone Android à un PC : notifications, SMS, presse-papiers,
> fichiers, miroir d'écran — puis il diagnostique le PC lui-même, avec la mesure qui
> justifie chaque conclusion. Sa6i Clean est un nettoyeur que nous n'avons pas écrit :
> nous avons prouvé son contenu, fermé un chemin de suppression dangereux, et l'avons
> intégré dans la même fenêtre. Rien ne quitte les deux appareils. »

### 2.3 The five-minute stage pitch — 8 slides

Total 300 seconds. The right-hand column is what you actually say; keep to it.

| # | On screen | Say (~seconds) |
| --- | --- | --- |
| 1 | Two stills: the phone home screen, the PC Monitor page | "Two devices. One carries your life, the other does your work. I build the bridge — and then I make the PC tell the truth about itself." (20) |
| 2 | The three questions: *what is slow · why · is it safe to clean* | "Every support conversation I have had comes down to these three. Existing tools answer one each, and none of them show their work." (25) |
| 3 | Link features, one line each, no icons | "Notifications you can reply to, SMS and calls, clipboard both ways, transfer that resumes, mirroring with control, phone as webcam. This half is built and tested." (40) |
| 4 | Monitor page + one finding with its evidence line | "Then the PC measures itself. Ten rules. A finding cannot exist without the measurement behind it — this line here is the reason it fired, not a sentence I wrote." (45) |
| 5 | The `MetricState` idea: value / unknown + reason / unsupported + reason | "The rule that shaped the whole design: a missing measurement is not a zero. It carries why it is missing, and the page shows that instead of a flat line at the bottom." (35) |
| 6 | Clean, in the same window, plus the guard diagram | "The cleaner is not ours. We proved what's inside it, then found a deletion path that follows a redirected folder — a junction above a cache root — and closed it." (45) |
| 7 | The two-column honesty table: verified / not verified | "What's verified is verified by a test or a hash. What isn't, is written down as not verified. No cleanup has ever been run — and I'd rather tell you that than have you find out." (45) |
| 8 | One line: *measure, explain, and show the work* | "Sa6i Link is a bridge that diagnoses, and a cleaner that can prove what it touches. Both halves are the same promise: say only what you can show." (25) |

**The line that must land:** slide 5. If they remember one thing, it is that a
missing number is not a zero. Slide 7 is what makes slide 5 believable.

### 2.4 The twelve-minute technical talk — 10 slides

For a technical track, a jury with engineers, or a university defence.

| # | Slide | Content and speaker notes |
| --- | --- | --- |
| 1 | Title + the one-line claim | Same as §2.1. Say who you are, and that this is a very small team with a sandbox and one Windows 7 machine. |
| 2 | The architecture | Show `docs/architecture/MODULE-MAP.md`'s diagram: `intel` (no OS, no Qt, no HTTP) → `intel-win` (Windows collectors) → shell (Qt/QML); `core` (transport) separate; CLI depends on everything and proves it headless. |
| 3 | Why the boundaries are compile-time facts | "Diagnostics must not require a phone, a pairing or a transport. If telemetry lived in `core`, every diagnostics fix would be a protocol change and 'does the doctor work without a phone?' would be a runtime question. It is now a compile error." |
| 4 | The model | `Snapshot` → `metrics()` publishes 19 path shapes. `MetricState::{Value, Unknown(reason), Unsupported(reason)}`. A path that a snapshot does not publish cannot be cited as evidence. |
| 5 | The rules | Ten rules, each a pure function of `(snapshot, store, thresholds)`. Every rule declares `requires`; a config file may not cite a path that no snapshot publishes. Evidence with `from_seq`/`to_seq`/`held_for_ms`: a finding is re-derivable from recorded samples. |
| 6 | The front-end | TOML overrides numbers only — never identity. The loader refuses: an unknown rule id, an unknown key, another rule's key, an unpublished path, a scenario that does not exist, a rule claimed twice, a percentage outside 1–99.9. And the shipped files must flatten to exactly the compiled defaults, so the front-end provably changed no verdict. |
| 7 | The fixtures | 28 fixtures, each a machine behaviour and its expected findings, including the near-misses: 89.9 % held past the window, a pid recycled mid-window, an idle disk reading 0 ms per transfer, a window broken in the middle. A rule with no firing case *and* no near-miss does not ship. |
| 8 | Privacy as a test, not a promise | 871 test functions across the workspace; `tests/privacy.rs` reads `Cargo.lock`, builds the dependency graph by name, and fails if either intel crate can reach a socket-capable crate (closures of 62 and 74 crates). The network stack is not "not used" — it is not reachable. |
| 9 | Clean: the hard part | Three screens, three sentences: (a) provenance — packaged JS matched upstream source byte for byte, including `main.js`, `preload.cjs`, the React bundle; (b) hosting — hash-pinned executables, a native child in a same-process clipping container so a foreign process cannot paint over the header; (c) the guard — upstream followed a junction above a cache root on real NTFS; ours refuses it; protected paths (`Windows`, `Desktop`, `.ssh`) are blocked. |
| 10 | What is not done, and the plan to close it | Read the "not verified" column aloud. Then one slide of what closes it: `scripts/verify-m1.ps1` for the numbers, a disposable Windows installation for cleanup, signing and a rights-holder grant for distribution. |

**Timing:** 60 s per slide for 1–2, 90 s for 3–9 is too slow — budget 70 s average
and give slide 9 ninety seconds.

---

## 3. Modalities — the same truth in six formats

### 3.1 Live stage: the beat sheet

**Short slot (5 min).** Open with the two stills (5 s), give the 30-second answer,
then spend 2 minutes on *one* diagnostic finding with its evidence line, then 90
seconds on Clean, then the honesty table and the closing line. Never list features
on stage; point at two and say the rest are in the README.

**Long slot (12–15 min).** Follow §2.4. Stop at minute 11 whatever happens — leave
time for the one question that always comes.

**Rule for both:** every claim on stage is a sentence you could defend for 60
seconds. If you cannot, it is a bullet for the poster, not a sentence for the stage.

### 3.2 Poster session — layout

One A1 sheet, portrait, read at 1.2 m distance.

```
┌─────────────────────────────────┬───────────────────────────────────┐
│ SA6I LINK  phone - PC, and the truth about the PC                   │
│ Sa6i Clean someone else's cleaner, provably hosted                  │
├─────────────────────────────────┼───────────────────────────────────┤
│ WHAT IT DOES                    │ HOW IT IS BUILT                   │
│ · notifications, SMS, calls     │ intel      measure: no OS, no Qt  │
│   clipboard, both ways          │ intel-win  Windows collectors     │
│ · resumable file transfer       │ core       transport, iroh/QUIC   │
│ · mirroring, webcam             │ shell      Qt 6 / QML over cxx-qt │
│ · measures the machine          │ CLI        proves it headless     │
│ · 10 rules, with evidence       │                                   │
│ · one window, one Back          │                                   │
├─────────────────────────────────┼───────────────────────────────────┤
│ THE IDEA                        │ VERIFIED / NOT VERIFIED           │
│ a missing number is not a zero: │ ✓ transfer, mirroring, pairing    │
│ it carries the reason.          │ ✓ 10 rules, 28 fixtures           │
│ a finding without evidence      │ ✓ privacy: no socket reachable    │
│ is not a finding.               │ ✓ cleaner JS = upstream source    │
│                                 │ ✓ guard stops redirected delete   │
│                                 │ ✗ numbers vs Task Manager         │
│                                 │ ✗ any real cleanup, ever          │
├─────────────────────────────────────────────────────────────────────┤
│ one screenshot: the Monitor page, one finding open                  │
│ one screenshot: the cleaner inside the same window                  │
│ QR: repository + the verify command                                 │
└─────────────────────────────────────────────────────────────────────┘
```

The two columns people actually stop at are the right-hand ones. Put them at
eye height.

### 3.3 Live demo — four minutes, in order

Do the boring thing first; it makes the interesting thing credible.

| Beat | Do this | If it fails, say this |
| --- | --- | --- |
| 1 (30 s) | `sa6i-link intel snapshot --json` in a terminal (or `cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- --json`). Scroll one screen. | "This is the same payload the window renders — one JSON object, every number with the reason it exists." |
| 2 (40 s) | Open the Monitor page. Point at one tile and one *missing* tile; read its reason aloud. | "Notice it doesn't say zero. It says *not measured yet* — that's the whole design in one tile." |
| 3 (60 s) | Show a finding with its evidence: metric path, observed value, threshold, held-for. | "I didn't write this sentence. The rule did, from these three numbers." |
| 4 (40 s) | Show the rules file `core/sa6i-link-intel/rules/disk.toml` next to the finding's threshold. | "This is where 90 % comes from. Change it, and the finding cites the new number, not the old one." |
| 5 (60 s) | Phone → PC: send a file, or mirror the screen. | Fall back to a screenshot: a recording that plays is better than a demo that apologises. |
| 6 (50 s) | Clean, inside the same window. Do **not** press a destructive button. Show the guard explanation. | "I'm not going to run a cleanup in front of you. That's not caution for the demo — it's the state of the project." |

**If the demo machine is Windows 7:** the Qt window will not run there — Qt 6
requires Windows 10 1809 or later. Show the CLI on that machine and the window on
video or on a borrowed laptop, and say so in one sentence before anyone notices.

### 3.4 Video — shot list

60–90 seconds, no narration over music, screen recordings only.

1. Phone screen, a notification arriving, reply from the PC (8 s).
2. Drag a 2 GB file; pause; resume (10 s).
3. Mirroring, one gesture of control (8 s).
4. Monitor page, cut to a *missing* tile and its reason (10 s).
5. A finding and its evidence line, zoomed (8 s).
6. Clean inside the same window, cursor moving, no destructive click (8 s).
7. End card: the two-line claim, the repository URL, and the words *not yet
   verified on hardware* — put that on the card, in small type, and it becomes a
   credibility asset instead of a trap.

### 3.5 Written submission

**Abstract (150 words).**

> Sa6i Link connects an Android phone to a Windows PC: notifications you can reply
> to, SMS and calls, a shared clipboard, resumable file transfer, screen mirroring
> and the phone as a webcam. The same application measures the PC it runs on — CPU,
> memory including commit charge and hard faults, every volume, disk latency, GPU and
> the heaviest processes — and runs ten rules over those numbers. Every finding
> carries the measurement that produced it, and a measurement that failed is shown
> as the reason it failed rather than as zero. Sa6i Clean, a separately verified
> hosted build of the Cleanly cleaner, runs inside the same window behind guards that
> refuse deletion through redirected folders. Nothing is sent off the two devices,
> and a test reads the dependency graph to prove it. The repository records what has
> been verified and what has not.

**"How it was built" (400 words).** Use the four paragraphs of §4 in order, but cut
every sentence that has no number in it.

### 3.6 The Q&A round — the four-part answer

Every answer, in this order, in under 45 seconds:

1. **The claim** — one sentence, no hedging.
2. **The evidence** — a test, a hash, a command, a file path. Something they could
   check without you.
3. **The limit** — what that evidence does *not* prove. This is the part that makes
   judges trust parts 1 and 2.
4. **What closes the gap** — one sentence, concrete.

Example, asked "does it work on Windows 7?":

> "The CLI does; the window cannot. — The CLI is built for the `x86_64-win7-windows-msvc`
> target with nightly `-Z build-std`, and the collectors use only standard-user APIs.
> — What I have not done is run it there, because that machine has no Rust toolchain
> and can't install one. — `scripts/verify-m1.ps1` on that machine closes it in one
> command; the record lands in `target/m1-verification.md`."

Notice that the limit sentence is not an apology. It is the part that makes the
first sentence worth believing.

---

## 4. How it is built — Sa6i Link

### 4.1 The shape

```
        ┌───────────────────── shell (GPL-3.0-or-later) ─────────────────────┐
        │  Qt 6 / QML  ──  cxx-qt bridge  ──  IntelHost                     │
        │  13 pages        (Rust structs → QML)                             │
        └───────────┬───────────────────────┬──────────────────────────────┘
                    │                       │
        ┌───────────▼─────────┐   ┌─────────▼──────────────┐   ┌──────────┐
        │ sa6i-link-intel-win │   │ sa6i-link-core         │   │  CLI     │
        │ Windows collectors  │   │ link · pairing ·       │   │ headless │
        │ (PDH, Win32, NT)    │   │ transfer · mirroring   │   │ proof    │
        └───────────┬─────────┘   └─────────┬──────────────┘   └──────────┘
                    │                       │
        ┌───────────▼─────────┐   ┌─────────▼──────────┐
        │ sa6i-link-intel     │   │ sa6i-link-protocol │  (CBOR over iroh/QUIC)
        │ model · rules ·     │   │ sa6i-link-adb      │
        │ store · findings    │   └────────────────────┘
        │ MPL-2.0, no OS,     │
        │ no Qt, no HTTP      │
        └─────────────────────┘
```

Two licence halves on purpose: the diagnostics core is MPL-2.0 so it can be reused
or republished, the shell is GPL-3.0-or-later, and `deny.toml` encodes that the
dependency direction may never reverse.

### 4.2 The crates, and what each may not do

| Crate | Owns | May not |
| --- | --- | --- |
| `sa6i-link-intel` | model, 10 rules, store, findings, TOML loader | touch an OS API, Qt, or a socket |
| `sa6i-link-intel-win` | the Windows collectors | depend on `core` — diagnosis must not need a phone |
| `sa6i-link-core` | link, protocol, pairing, transfer, mirroring | know that diagnostics exist |
| `sa6i-link-protocol` | CBOR messages, capability registry | anything platform-specific |
| `sa6i-link-adb` | the Android plumbing | — |
| `sa6i-link-ffi` | UniFFI surface for Kotlin | desktop-only features |
| `desktop/app` | Qt/QML shell, 13 pages, bridge | be referenced from any core crate |
| `sa6i-link-cli` | headless proof: snapshot, JSON, history | need Qt |

### 4.3 The five invariants, and the test that enforces each

1. **A missing measurement is a value, not a zero.** `MetricState::{Value,
   Unknown(reason), Unsupported(reason)}`; `metrics()` emits nothing for a metric it
   does not have, so a rule physically cannot cite it.
   *Enforced by:* the fixtures' `null` volumes and `Unknown` encodings, and every
   rule's early return.
2. **A finding without evidence is dropped.** `evaluate()` filters
   `is_supported()` and logs the drop, rather than showing a claim.
   *Enforced by:* `Finding::is_supported` plus the scenario test asserting every
   finding has evidence.
3. **Evidence must be a published path.** Each rule declares `requires`, and a test
   asserts every declared path is a shape `metrics()` can emit — otherwise `requires`
   is a comment.
   *Enforced by:* `every_declared_input_is_a_path_a_snapshot_publishes`.
4. **The front-end changes numbers, never verdicts.** The shipped TOML files must
   flatten to exactly `Thresholds::default()` — 21 fields — so every finding from
   every fixture is byte-identical to the compiled defaults.
   *Enforced by:* `the_shipped_files_restate_the_compiled_numbers`.
5. **Nothing leaves the machine.** `tests/privacy.rs` builds the dependency graph
   from `Cargo.lock` by name and fails if either intel crate can reach a
   socket-capable crate.
   *Enforced by:* the privacy test itself — 62 and 74 crates in the two closures.

### 4.4 The measurement → rule → evidence chain

- **Collect** — `GetSystemTimes`, `GlobalMemoryStatusEx`, `GetDiskFreeSpaceExW`,
  `NtQuerySystemInformation` with `PROCESS_QUERY_LIMITED_INFORMATION`, and three
  separate PDH queries (disk, memory, GPU). Standard-user APIs only; no elevation
  is requested and no manifest asks for it.
- **Model** — one `Snapshot` per second, 19 published path shapes, plus identity
  (a process's creation stamp) that travels in the sample because a pid is not an
  identity and an `f64` cannot hold a FILETIME.
- **Judge** — ten rules over the snapshot and the store. "Sustained" means every
  sample in the window satisfies the predicate; one quiet sample breaks the claim.
  An idle disk reading 0 ms and an idle machine reading 0 pages/s are readings, not
  findings.
- **Explain** — the finding renders its own evidence: metric path, observed value,
  threshold, and how long it held, with the sample range so it can be re-derived.

### 4.5 The rules front-end, and why a config file may not invent a rule

A TOML file may change a number and may restate identity. It may not add a rule, a
key, or a citation. The loader refuses, naming the rule and the key: an id the build
does not have, an unknown key (so `warn_pct` fails loudly instead of silently keeping
the default), a key belonging to another rule, a `requires` path nothing publishes, a
percentage outside 1–99.9, a warning at or above its critical, a duration that is not
`<number><s|m|h|d>`, the same rule twice, or a fixture claimed by two rules.

With no file present, the compiled defaults apply: the front-end is an override, not
the only source of truth, so the app cannot start with zero rules.

### 4.6 What is not built — say it in the same breath

- The **Assistant** (a local Ollama explainer over the findings) is not implemented.
  It is designed as an HTTP leaf: reachable only from the shell, never from a core
  crate, so a private build can ship with the provider compiled out.
- The **Security** module (config and persistence checks) is not implemented.
- The **five-machine false-positive review** has not happened. It is the milestone's
  exit criterion and it is the one thing no sandbox can substitute for.

---

## 5. How it is built — Sa6i Clean

### 5.1 Say what it is before anyone asks

> "It's not ours. Cleanly 0.2.0, by 0xCodez, packaged Electron. We patch branding and
> we host it in our window. The cleaning code is theirs, and that's exactly why the
> provenance work matters."

Say it first. A judge who discovers it after asking "did you write this?" hears
"he tried to hide it"; a judge who hears it in the opening believes everything else.

### 5.2 Provenance — the part that is engineering

- The packaged `app.asar` was extracted and compared with a local production build of
  the public source at tag `v0.2.0`, commit `b62bef4`.
- **Every packaged file matched byte for byte**, including `dist-electron/main.js`,
  `preload.cjs` and the React bundle. Only `package.json` (pruned fields) and
  `dist/index.html` (one blank line) differ, both checked by content.
- The executable is the upstream Electron binary; only its PE icon resources and the
  embedded ASAR integrity hash changed. Windows metadata and signature state are
  unchanged — and it is **unsigned**.
- The archive is hash-pinned entry by entry: 1,235 entries checked, CRCs pass,
  classic ZIP without ZIP64.

### 5.3 Hosting — same window, not a second window

The requirement was one window: a button switches the main window to the Clean
layout. That is a cross-process rendering problem, and the interesting failures were
all visual.

- The cleaner is launched as a native child, hash-pinned by exact digest before
  launch, and reparented into a **same-process clipping container** sized to the Qt
  viewport — so a foreign process cannot paint or receive input outside it.
- Hiding is ordered: the container is hidden on the host thread *before* the
  asynchronous child hide, and the tracked process is closed and reaped before the
  container is destroyed.
- A separate "restricted" build blocks 12 IPC routes, including cleanup and uninstall,
  and the host verifies that executable's exact hash before hosting it. That is not a
  sandbox and the docs say so.

### 5.4 The guard — a real bug, found by writing a probe

The upstream `deleteCacheEntry(target, root)` protected the *target* (rejects a
symlink/junction and re-checks containment after `realpath`) but never canonicalised
`root`. So a redirect sitting **above** a cache root looked like an ordinary directory
and its contents were deleted *through* it.

Evidence, in the repository's own words: on real NTFS on a disposable Windows runner,
unpatched upstream followed a junction above the cache root; the guarded build refuses
it and still cleans ordinary folders, including 8.3 and differently-cased spellings.
Protected paths (`Windows`, `Desktop`, `.ssh`) are blocked; deletion stays inside the
redirected subtree rather than escaping it.

That is the single best technical story in the project: a third-party app with a
plausible-looking guard, a probe that showed the guard's blind spot, and a fix
verified against synthetic files with sentinels.

### 5.5 What is not proven — the sentence you must not forget

- **No cleanup, Recycle Bin emptying, uninstall or startup change has ever been run** —
  not on Windows 7, not anywhere. Several of them are permanent, via `fs.unlink`, with
  no undo.
- No Windows 10/11 desktop run and no Windows 7 run *by us*. The deletion functions
  were exercised on a Windows Server runner with synthetic files: evidence about NTFS,
  not about the app's interface, the Recycle Bin's shell integration, or Windows 7.
- Windows 7 needs VxKex and a bundled `cldapi.dll` shim; the 40-pixel header clearance
  is a visual workaround and the underlying compositor offset is still unexplained.
- Redistribution rests on the rights holder's permission as reported to the project;
  the upstream repository is marked `UNLICENSED` and no written grant is in the repo.

---

## 6. The Q&A bank

Answer shape: claim, evidence, limit, what closes it. Keep to 45 seconds.

### A. Why this exists

**A1. What problem are you solving?**
Three questions people actually ask: *what is slowing my PC down*, *why*, and *is it
safe to clean this up*. Existing tools answer one each and none of them show their
work. Sa6i Link is one place that measures, explains, and can prove the explanation.

**A2. Why you?**
Because I refused the shortcut. The easy version of this app shows a nice number and
guesses a cause. This one won't render a failed measurement as zero, and drops a
finding that has no evidence — the awkward decisions cost weeks and they are the
product.

**A3. Who is it for?**
First: the person who is the family's IT department, on a Windows 7 or 10 machine
that just got slow. Second: anyone who has been told *"it says out of memory and there
is plenty of RAM"* — which is exactly the commit-charge rule.

**A4. Why now?**
Windows 10 left support in October 2025, and it did not stop working: the population
of machines that are still perfectly usable is enormous, and "buy a new PC" is not an
answer for most of their owners. Measuring correctly matters more when people keep what
they have.

### B. What it does / how it differs

**B1. Isn't this KDE Connect / Phone Link / scrcpy / LocalSend?**
Each of those is one lane: KDE Connect (notifications, clipboard), scrcpy (mirroring),
LocalSend (transfer), Phone Link (Microsoft ecosystem). Sa6i Link does those in one
bridge with one capability matrix — and then diagnoses the PC, which none of them
does. The diagnosis is the half nobody else is in.

**B2. Why two products in one presentation?**
They are one thesis: *only say what you can show*. Link shows you the phone, Monitor
shows you the machine, Clean shows you what it touched. Also, honestly: Clean exists
because a user asked for it in the same window, and the engineering answer was to
prove what we were hosting first.

**B3. What is the difference between Monitor and Task Manager?**
Task Manager shows numbers. This shows numbers *and* the rule that interpreted them,
with the threshold, how long it held, and the sample range — so a finding is
re-derivable from the recorded history. And it says *why* a number is missing instead
of drawing zero.

**B4. Ten rules seems few.**
Ten rules that each ship with a firing case and a near-miss, versus a hundred that
fire on every machine. The near-miss is the expensive one: 89.9 % held past the
window, a pid recycled mid-window, an idle disk reading 0 ms per transfer, a
half-hour window with one quiet minute in the middle.

**B5. What does it cost the machine?**
The collector is designed for 1 Hz under an explicit budget: `--samples 1800
--interval-ms 1000 --budget` prints the achieved rate, the per-sample cost and this
process's own CPU share, and exits 3 on a miss. That criterion is written; it has not
been run on your machine yet.

**B6. Can it run on a phone-only household?**
No, and that is fine: the diagnosis half is desktop-only by design — the intel crates
have no transport dependency, so the doctor works with no phone paired at all.

### C. Architecture and language choices

**C1. Why Rust?**
Two reasons: measurement code that must not have a garbage collector pause in the
middle of a timing, and a single core usable from three front-ends — Qt desktop,
Android via UniFFI, and a CLI. The CLI is not a testing afterthought: it is the proof
the core is headless.

**C2. Why Qt and not Electron for the shell?**
The shell is where the low-level work meets the UI: native child windows, a virtual
camera, a Win32 clipping container. cxx-qt 0.10 generates Qt 6 code, so the app's
minimum is Windows 10 1809 — and that is the reason Windows 7 is CLI-only.

**C3. Then why host an Electron app inside it?**
Because the cleaner exists and writing a safe cleaner from scratch is a much bigger
project than hosting one behind guards. The honest trade: we accept a second runtime
in exchange for not writing deletion code ourselves, and we pay for it with hash
pinning and provenance work.

**C4. What is the single most important design decision?**
`MetricState`. A number, or the reason there isn't one, as a type. It removed the
whole class of "the graph shows 0 % because the read failed" bugs, and it forced the
UI to have a way to say *not measured* — which then forced the rule engine to have a
way to say *no opinion*.

**C5. How do the phone and PC agree on what is possible?**
A capability matrix computed in the core from both devices' advertised capabilities,
OS versions, power level and per-device toggles, and emitted only when it changes.
Both apps render from the same matrix, so they cannot disagree about what works.

**C6. What is the wire format?**
CBOR over iroh's QUIC transport. Capability ids are declared once, in the core's
feature registry, and documented in the protocol notes so both ends spell them the
same. iroh is pinned at 1.3 deliberately: 1.4 closes a connection on a buffered
stream, which breaks a paused transfer.

**C7. Why is there a TOML front-end at all?**
Because a threshold nobody can change without a compiler is a threshold nobody will
calibrate. The loader's job is to make calibration safe: numbers may change, identity
may not, and the shipped files are proven to produce byte-identical findings.

**C8. What did you have to fix that surprised you?**
A function called `seconds()` that also returned a rate. It was correct and it was a
units bug waiting to happen; renaming it `number()` was cheaper than the bug. Same
family: `Avg. Disk sec/Transfer` reads 0 on an idle disk and `Pages Input/sec` reads 0
on an idle machine — both are readings, neither can be a finding.

### D. Diagnostics: correctness and trust

**D1. Have you compared your numbers with Task Manager?**
No. That is the first unresolved exit criterion and I will not pretend otherwise. —
The collectors read the same PDH counters and the same Win32 APIs Task Manager reads. —
What is missing is the side-by-side run. — `--samples 60 --interval-ms 1000 --average`
next to Task Manager's Performance tab, on one machine, closes it.

**D2. Then why should a judge believe any of it?**
Because the design is checkable without trusting me: 28 fixtures with expected
finding sets, evidence that carries `from_seq`/`to_seq` so a finding can be
re-derived, and a repository that says which of the six exit criteria are closed. If
you only believe the verified column, the product still stands.

**D3. How do you know the rules don't fire on healthy machines?**
Every rule ships a near-miss fixture, and the scenario test asserts the *exact* set
of findings — not "at least" — so a new rule that fires on an old fixture breaks the
build. What is still owed is the five-machine review: five real machines, one row per
finding, "was it true and why".

**D4. What is the false positive you are most afraid of?**
A build. `cpu.sustained_high` fires at 90 % for ten minutes and a compile is exactly
that. The rule is right; the *wording* has to make clear it is an explanation, not an
accusation. That is a text problem I can only really fix with the review.

**D5. What if PDH is broken on the machine?**
Then those paths carry `Unknown(CollectorFailed)` and the rules over them stay
silent — the page says the counter could not be read rather than showing a calm
machine. Separate queries for disk and memory exist so one broken counter object does
not take the other's number with it.

**D6. How long is the history?**
4096 samples at 1 Hz — about 68 minutes — which is why every window fits today, and
why the wording never implies a background service. A window the store cannot span
returns *no answer*, never "passes".

### E. Privacy and security

**E1. What does it send off the machine?**
Nothing, from the diagnostics half, and that is a test rather than a policy: the
privacy test parses `Cargo.lock`, builds the dependency graph by crate name, and fails
if `sa6i-link-intel` or `sa6i-link-intel-win` can reach anything socket-capable. Today
those closures are 62 and 74 crates and both are clean.

**E2. And the link half?**
It is peer-to-peer between your phone and your PC over iroh — direct on the LAN, relay
only when you turn Away mode on — with pairing. There is no account and no telemetry
endpoint. The list of crates allowed to open a socket is a ratchet in a test, so
adding one is a visible, deliberate edit.

**E3. Is the local AI sending my data anywhere?**
There is no local AI yet. The design puts any provider behind the shell, as an HTTP
leaf on `127.0.0.1:11434`, never behind a core crate — so a build can ship with the
provider compiled out, and the product is complete without it.

**E4. Does it need administrator rights?**
No. No elevation API is called and no manifest requests it; the collectors use
standard-user APIs only, which also means some readings are simply unavailable and
say so. That is a design choice, not a limitation to be fixed later.

**E5. Where is the config file stored, and can it be tampered with?**
The loader is proven but not yet wired to a runtime path — the search order needs a
Windows machine to test. Being honest about that matters more than guessing: a config
that fails quietly is worse than no config.

**E6. Could a malicious TOML file do something bad?**
Not much, by construction: it cannot add a rule, add a key, or cite a path the
snapshot does not publish, and every refusal names the rule and the key. The worst it
can do is make an existing rule stricter or looser within declared ranges.

### F. Sa6i Clean: licensing, safety, blame

**F1. You didn't write the cleaner.**
Correct, and it is the first thing I say. Cleanly 0.2.0 is by 0xCodez, and its
repository is marked `UNLICENSED` — which is why the questions below exist at all.

**F2. Do you have permission to redistribute it?**
The rights holder gave permission, as recorded to the project; no written grant is in
the repository, and the release notes name that as an open item. If the grant cannot
be documented, the honest move is to ship the *host* and let the user supply the
cleaner — the integration does not depend on redistributing it.

**F3. Why should we trust a patched binary?**
Because the patch is arithmetic, not a claim: the packaged JavaScript matches the
public source at a named commit byte for byte, including the main process, the preload
and the React bundle; the executable is the upstream Electron binary with only its
icon resources and the embedded ASAR digest changed. Reproducible by one script in the
repository.

**F4. What if it deletes the wrong thing?**
I cannot tell you it won't, and that is why no cleanup has ever been run. What I can
tell you: ordinary cache deletion uses `fs.unlink` with no Recycle Bin and no undo;
the paths come from category IDs inside the main process, so the renderer cannot ask
for an arbitrary path; the target is checked against symlinks and junctions and
re-checked after `realpath`; and a redirected *root* — the gap we found — is now
refused.

**F5. How did you find the redirect bug?**
By not believing the guard. I wrote a probe with synthetic files, one temporary
directory, Electron and drive enumeration stubbed out, and it printed three lines:
`linkTargetRefused: true`, `redirectedRootAcceptedAsRealDirectory: true`,
`deletedThroughRedirectedAncestor: true`. Then I reproduced it on real NTFS on a
disposable Windows runner.

**F6. Is the cleaner sandboxed?**
No, and the documentation says so in those words. A fresh `--user-data-dir` per launch
isolates settings, not files; the cleaner can reach other user and system paths. A
sandbox is future work.

**F7. Why is it unsigned?**
Because signing costs money and identity checks and I would rather spend the remaining
effort on verification. The consequence is named in the release notes: SmartScreen and
unknown-publisher warnings, and plausible antivirus false positives from the patched
binaries.

**F8. What happens on Windows 7?**
The cleaner needs VxKex plus a bundled `cldapi.dll` shim, and the Qt window cannot run
there at all — Qt 6 requires Windows 10 1809 or later. The CLI is the piece that keeps
Windows 7 first-class, and it is built for that target on purpose.

### G. Engineering process — including the awkward one

**G1. How much of this is AI-assisted?**
A lot of the writing and a lot of the code were produced with AI assistance, and the
repository is built to survive that: every milestone document records what has been
verified and what has not, and the checks are executable rather than assertions in
prose. The judges' real question is "can you defend it", and the answer is: ask me
about any invariant and I will show you the test that enforces it and tell you what
that test does not prove.

**G2. If it was never compiled, how do you know it compiles?**
I don't — and the milestone documents say so in those words. What I can show is that
the logic was checked another way: the ten rules were re-implemented independently and
run against all 28 fixtures, the ten TOML files were parsed and shown to flatten to
the 21 compiled thresholds, and structs were brace-checked for fields that a compiler
would have caught. That is not a build. It is why the first `cargo test` on a real
machine is the next milestone, not a formality.

**G3. What was the hardest bug?**
Two candidates. The junction above a cache root — plausible guard, real blind spot, and
a probe that proved it on real NTFS. And pid identity: Windows recycles pids, so a rule
that accumulates ten minutes per pid credits one program's work to another; the fix is
carrying the creation stamp into the sample, which is a model change, not a rule change.

**G4. What did you cut?**
The Assistant, the Security module, and the first version of the test that asserted a
JSON shape two fields out of date — that one is a good story: a test that had been
failing silently since the model grew, found only by re-reading the struct. Being
honest about silent failures is the whole discipline.

**G5. What is the process?**
Milestones with written exit criteria: M0 the audit, M1 the sampler and the Monitor
page, M2 the rules and the TOML front-end. Nothing in M2 ships until M1's criteria
close on a real PC — a rule is a sentence about a machine, and writing rules against
numbers nobody compared with Task Manager is how a diagnostics tool ends up
confidently wrong. That gate was waived exactly once, for the loader, because its
proof needs no machine.

**G6. How do you keep from overclaiming?**
One rule: every milestone document has a "what is not verified" section, and it is
written before the demo, not after the question. The release-readiness file for Clean
is literally a table of what has evidence and what does not.

### H. Delivery, money, scale

**H1. What would you do with a year and a budget?**
In order: (1) the five-machine review and the Task Manager comparison — nothing else
matters until the numbers are trusted; (2) a disposable Windows installation to test
removal safely, with backups and sentinels; (3) signing and a written redistribution
grant; (4) the Security module and the local Assistant, which are designed and empty.

**H2. How does this become sustainable?**
Two honest models. Free and open source with paid signing/support for small IT shops;
or a paid "family IT" tier where the diagnostic report is what a person can send to
whoever helps them. I would not gate the measuring — the measuring is the argument.

**H3. Does it scale to a company's 1,200 PCs?**
Not yet, and deliberately: no agent, no fleet management, no central collection. The
history is local SQLite and the CLI emits JSON, which is the shape that would come
first if anyone asked.

**H4. What is the smallest thing that proves the thesis?**
`sa6i-link intel snapshot --json` on a machine with a broken counter: the JSON has the
reason, the page shows the reason, and the rule stays silent. One command, one honest
gap.

**H5. How big is the team?**
Small enough that the repository has to be the memory: ADRs, milestone reports, and a
status file that is worth more than another pair of hands who has not read it. That is
not modesty — it is why the "what is not verified" sections exist.

**H6. What does it cost to run?**
Nothing to operate: no servers, no accounts, no telemetry. The costs are signing
certificates and test hardware.

### I. The brutal five

**I1. "This is a wrapper around other people's tools."**
Half of it is, and I say which half. Link stands on iroh, Qt and the platform APIs;
Clean is explicitly a hosted third-party app. What is mine is the layer that decides
what is true: the model, the rules, the evidence, the privacy ratchet, the provenance
work, and the guard on a deletion path the upstream project never fixed.

**I2. "Then what is actually novel?"**
Three things: a diagnostics engine where a finding cannot exist without a measurement
and a missing measurement cannot become zero; a TOML front-end that provably cannot
change a verdict; and a hosted third-party cleaner whose binary is provably the source
it claims to be, behind a guard found by probing rather than assuming.

**I3. "Why should we give this the prize?"**
Because it is the only submission you will see today whose documents tell you what it
does not do — and because the thing it does, it does with evidence you can re-run. If
you want the flashiest demo, choose someone else. If you want the one that would still
be true six months from now, this is it.

**I4. "Your own documents say it isn't verified. Why present it?"**
Because the alternative — presenting it as finished — is the failure mode this project
exists to prevent. Every number you have seen is accompanied by whether it has been
checked on hardware. That is not a weakness in the pitch; it *is* the pitch.

**I5. "What would make you withdraw it?"**
If the numbers fail the Task Manager comparison, the rules go back to calibration and
the demo becomes the method, not the findings. If the cleanup cannot be made safe on a
disposable machine, Clean ships as a host that opens the user's own copy — or not at
all.

---

## 7. Claims discipline

### 7.1 The credibility table — put this on a slide

| Claim | State | Evidence in the repository |
| --- | --- | --- |
| Phone ↔ PC features work | **in use on real devices** — the shipped Windows binary is a patched build | the link half; capability matrix tests |
| 10 rules, 28 fixtures | **written and simulated** | `core/sa6i-link-intel/tests/scenarios/` |
| TOML can never change a verdict | **proven by test** | `the_shipped_files_restate_the_compiled_numbers` |
| Nothing leaves the machine | **proven by test** | `tests/privacy.rs`, closures of 62/74 crates |
| Cleaner JS = upstream source | **proven byte for byte** | `verify_upstream_equivalence.py` at `b62bef4` |
| Guard stops redirected deletion | **proven on synthetic NTFS** | Windows runner run `45034853645` |
| Numbers match Task Manager | **not verified** | `docs/plan/M1-VERIFY.md` |
| Any real cleanup | **never run** | `sa6i/clean/RELEASE-READINESS.md` |
| Windows 7 window | **impossible** (Qt 6 needs Win10 1809+) | `docs/plan/WIN7.md` |
| Redistribution rights | **stated, not documented** | `SAFETY-REVIEW.md` |

### 7.2 Ten sentences to use verbatim

1. "A missing measurement is not a zero; it carries the reason it is missing."
2. "A finding that cannot show its evidence is dropped before it reaches the screen."
3. "The rule engine has no opinion about a machine it could not measure."
4. "Nothing leaves the machine, and that is a test that reads the dependency graph."
5. "The front-end may change a number; it may not change a verdict."
6. "Sustained means every sample in the window — one quiet sample breaks the claim."
7. "The cleaner is not ours. Here is how we proved what is inside it."
8. "We have never run a cleanup. That is the state of the project, not a disclaimer."
9. "The numbers have not been compared with Task Manager yet — that is the next
   milestone, and it needs one PC."
10. "Everything else on this slide is in the repository with the test that enforces it."

### 7.3 Five sentences that lose the room

1. "It's fully tested." — one question about hardware ends the credibility of every
   other answer.
2. "It works on Windows 7." — the *window* cannot; say "the CLI does" and explain the
   split before someone finds out.
3. "It cleans your PC safely." — nobody has run a cleanup, and some deletion is
   permanent.
4. "The AI explains the findings." — not built. It is designed and empty.
5. "We wrote the cleaner." — it is Cleanly, and the provenance work is the interesting
   part anyway.

---

## 8. Cheat sheet

**Numbers**

| | |
| --- | --- |
| Workspace | 11 crates, ≈160 000 lines of Rust, ≈31 000 of QML, ≈48 000 of Kotlin |
| Tests | 871 `#[test]` functions across the workspace |
| Diagnostics | 10 rules · 10 TOML files · 28 fixtures · 21 thresholds · 19 metric path shapes |
| Privacy | dependency closures of 62 and 74 crates, both socket-free |
| History | 4096 samples ≈ 68 minutes at 1 Hz |
| Cleaner | Cleanly 0.2.0, commit `b62bef4`; 1,235 archive entries, CRC-checked |
| Licences | core MPL-2.0, shell GPL-3.0-or-later, cleaner upstream `UNLICENSED` |

**Commands worth typing on stage**

```sh
# one payload, two front-ends
cargo run -p sa6i-link-intel-win --bin sa6i-intel-snapshot -- --json

# the rules, the fixtures, the privacy test
cargo test -p sa6i-link-intel

# the six exit criteria, on a Windows machine, in one command
.\scripts\verify-m1.ps1        # writes target/m1-verification.md

# the Windows 7 CLI
cargo +nightly -Z build-std=std,panic_abort --target x86_64-win7-windows-msvc \
  --release -p sa6i-link-cli
```

**Names, spelled for a slide**

- Sa6i Link — the product: one word, capital S, the numeral 6 in the middle. Spell it
  the same way on every slide, in every answer.
- Sa6i Clean — the hosted cleaner.
- Cleanly 0.2.0 by 0xCodez — the upstream project the cleaner comes from.
- iroh — the QUIC transport. cxx-qt — the Rust↔Qt bridge. Ollama — the (unbuilt)
  local model provider.
- `MetricState` — value, or the reason there is no value.
- NectarLink — the old name, still visible in some historical documents. If asked:
  a rename, and the older docs were kept rather than rewritten.

---

## 9. Rehearsal plan

1. **Read §2.1 out loud ten times** until it fits in 28 seconds without looking. It is
   the only thing you must never improvise.
2. **Run the demo twice on the machine you will use**, once with the network off and
   once with the cleaner already open. Write down the two things most likely to fail.
3. **Answer §6 at random** — have someone read question numbers, no re-reading the
   answer first. If an answer takes more than 45 seconds, cut the middle sentence.
4. **Rehearse the four-part shape on the three hardest questions** (D1, F4, I3) until
   the limit sentence comes out without flinching. Judges remember the flinch.
5. **Rehearse saying "I don't know"** once. It is the answer that makes the other
   twenty-nine believable.
