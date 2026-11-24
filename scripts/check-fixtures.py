"""Check the twelve rules against every fixture, and the TOML against the code.

    python3 scripts/check-fixtures.py

This compiles nothing. It re-implements the rules the way the Rust does - the same
predicates, the same windows, the same thresholds, the same integer arithmetic on
free space - runs every fixture through them, and checks that each TOML file names
only its own rule's keys and flattens back to the compiled defaults.

It is a second opinion, not a test suite: if the Rust and this file disagree, one of
them is wrong and neither is the truth. What it does prove is internal consistency -
every fixture produces exactly the findings it promises, every rule both fires and
stays quiet somewhere, and no two rules claim the same fixture.
"""

import json
import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
INTEL = ROOT / "core/sa6i-link-intel"
SCENARIOS = INTEL / "tests/scenarios"
RULES_DIR = INTEL / "rules"

DEFAULTS = {
    "disk_warn_percent": 90.0,
    "disk_critical_percent": 97.0,
    "disk_sustained_ms": 600_000,
    "memory_warn_percent": 90.0,
    "memory_sustained_ms": 120_000,
    "memory_commit_warn_percent": 90.0,
    "memory_commit_sustained_ms": 300_000,
    "process_cpu_percent": 80.0,
    "process_cpu_sustained_ms": 600_000,
    "memory_pages_per_second": 100.0,
    "memory_paging_sustained_ms": 300_000,
    "disk_slow_transfer_seconds": 0.1,
    "disk_slow_sustained_ms": 600_000,
    "process_growth_bytes": 256 * 1024 * 1024,
    "process_growth_window_ms": 1_800_000,
    "uptime_long_seconds": 1_209_600,
    "cpu_warn_percent": 90.0,
    "cpu_sustained_ms": 600_000,
    "core_pinned_percent": 95.0,
    "core_pinned_total_below_percent": 50.0,
    "core_pinned_ms": 600_000,
    "disk_fill_bytes": 5 * 1024**3,
    "disk_fill_window_ms": 1_800_000,
    "gpu_vram_warn_percent": 95.0,
    "gpu_vram_sustained_ms": 300_000,
}

REQUIRES = {
    "cpu.sustained_high": ["cpu.percent"],
    "cpu.one_core_pinned": ["cpu.core.*.percent", "cpu.percent"],
    "disk.low_free_space": ["volume.*.percent_used"],
    "disk.filling_fast": ["volume.*.free_bytes"],
    "gpu.vram_pressure": [
        "gpu.adapter.*.dedicated_used_bytes",
        "gpu.adapter.*.dedicated_limit_bytes",
    ],
    "memory.pressure": ["memory.percent_used"],
    "memory.commit_pressure": ["memory.commit_used_bytes", "memory.commit_limit_bytes"],
    "process.runaway_cpu": ["process.*.cpu_percent"],
    "process.memory_growth": ["process.*.working_set_bytes"],
    "disk.slow_transfers": ["disk.seconds_per_transfer"],
    "memory.paging": ["memory.pages_input_per_second"],
    "system.long_uptime": ["system.uptime_seconds"],
}

ALLOWED_KEYS = {
    "cpu.sustained_high": {"warn_percent", "sustained"},
    "cpu.one_core_pinned": {"warn_percent", "total_below_percent", "sustained"},
    "disk.low_free_space": {"warn_percent", "critical_percent", "sustained"},
    "disk.filling_fast": {"fill_mb", "sustained"},
    "gpu.vram_pressure": {"warn_percent", "sustained"},
    "memory.pressure": {"warn_percent", "sustained"},
    "memory.commit_pressure": {"warn_percent", "sustained"},
    "process.runaway_cpu": {"warn_percent", "sustained"},
    "process.memory_growth": {"growth_mb", "sustained"},
    "disk.slow_transfers": {"slow_ms", "sustained"},
    "memory.paging": {"pages_per_second", "sustained"},
    "system.long_uptime": {"long_after"},
}

SEVERITY = {
    "cpu.sustained_high": "Warning",
    "cpu.one_core_pinned": "Notice",
    "disk.low_free_space": "Warning",
    "disk.filling_fast": "Notice",
    "gpu.vram_pressure": "Warning",
    "memory.pressure": "Notice",
    "memory.commit_pressure": "Warning",
    "process.runaway_cpu": "Notice",
    "process.memory_growth": "Notice",
    "disk.slow_transfers": "Warning",
    "memory.paging": "Warning",
    "system.long_uptime": "Info",
}

MIB = 1024 * 1024
MEMORY_TOTAL = 16 * 1024 * MIB
VOLUME_TOTAL = 500 * 1024 * MIB
COMMIT_LIMIT = 24 * 1024 * MIB


def free_of(percent):
    return int(VOLUME_TOTAL * (100.0 - percent) / 100.0)


def snapshot(index, segment):
    volumes = []
    for spec in segment.get("volumes", []):
        percent = spec.get("percent_used")
        volumes.append(
            {
                "letter": spec["letter"],
                "kind": spec.get("kind", "fixed"),
                "percent": percent,
                "free": None if percent is None else free_of(percent),
            }
        )
    return {
        "seq": index + 1,
        "monotonic_ms": index * 1000,
        "cpu_percent": segment.get("cpu_percent", 20.0),
        "cores": segment.get("cores") or [],
        "memory_percent": segment.get("memory_percent", 50.0),
        "commit_percent": segment.get("commit_percent"),
        "pages": segment.get("pages_input_per_second"),
        "seconds_per_transfer": segment.get("disk_seconds_per_transfer"),
        "volumes": volumes,
        "uptime": int(segment.get("uptime_days", 2.0) * 86_400),
        "gpus": [
            {
                "instance": spec["instance"],
                "used": None if spec.get("used_mb") is None else spec["used_mb"] * MIB,
                "limit": None if spec.get("limit_mb") is None else spec["limit_mb"] * MIB,
            }
            for spec in segment.get("gpus", [])
        ],
        "processes": [
            {
                "pid": spec["pid"],
                "name": spec.get("name") or "proc%d.exe" % spec["pid"],
                "cpu": spec["cpu_percent"],
                "working_set": spec.get("working_set_mb", 100) * MIB,
                "created": spec.get("created", 0),
            }
            for spec in segment.get("processes", [])
        ],
    }


def samples_of(scenario):
    out = []
    index = 0
    for segment in scenario["segments"]:
        for _ in range(segment["minutes"] * 60):
            out.append(snapshot(index, segment))
            index += 1
    out.append(snapshot(index, scenario["segments"][-1]))
    return out


def held_for(store, window_ms, holds):
    last = store[-1]
    if last["monotonic_ms"] - store[0]["monotonic_ms"] < window_ms:
        return None
    start = last["monotonic_ms"] - window_ms
    if store[0]["monotonic_ms"] > start:
        return None
    for sample in reversed(store):
        if sample["monotonic_ms"] < start:
            break
        if not holds(sample):
            return None
    return True


def busiest_core(cores):
    best = None
    for index, percent in enumerate(cores):
        if best is None or percent >= best[1]:
            best = (index, percent)
    return best


def volume_of(sample, letter):
    for volume in sample["volumes"]:
        if volume["letter"] == letter:
            return volume
    return None


# --------------------------------------------------------------------- rules
def cpu_sustained_high(store, t):
    warn = t["cpu_warn_percent"]
    percent = store[-1]["cpu_percent"]
    if percent is None or percent < warn:
        return None
    if held_for(store, t["cpu_sustained_ms"], lambda s: s["cpu_percent"] >= warn) is None:
        return None
    return ("cpu.sustained_high", "Warning", "system")


def cpu_one_core_pinned(store, t):
    pinned, ceiling = t["core_pinned_percent"], t["core_pinned_total_below_percent"]
    total = store[-1]["cpu_percent"]
    if total is None or total >= ceiling:
        return None
    best = busiest_core(store[-1]["cores"])
    if best is None or best[1] < pinned:
        return None

    def holds(sample):
        return any(c >= pinned for c in sample["cores"]) and sample["cpu_percent"] < ceiling

    if held_for(store, t["core_pinned_ms"], holds) is None:
        return None
    return ("cpu.one_core_pinned", "Notice", "system")


def gpu_percent(adapter):
    """The adapter's share of its own memory, or None when that has no meaning."""
    if adapter["used"] is None or adapter["limit"] is None or adapter["limit"] == 0:
        return None
    return (min(adapter["used"], adapter["limit"]) / adapter["limit"]) * 100.0


def gpu_vram_pressure(store, t):
    warn = t["gpu_vram_warn_percent"]
    worst = None
    for adapter in store[-1]["gpus"]:
        percent = gpu_percent(adapter)
        if percent is None or percent < warn:
            continue
        if worst is None or percent > worst[1]:
            worst = (adapter["instance"], percent)
    if worst is None:
        return None
    instance, _ = worst

    def holds(sample):
        return any(
            a["instance"] == instance and (gpu_percent(a) or 0.0) >= warn
            for a in sample["gpus"]
        )

    if held_for(store, t["gpu_vram_sustained_ms"], holds) is None:
        return None
    index = [a["instance"] for a in store[-1]["gpus"]].index(instance)
    return ("gpu.vram_pressure", "Warning", "GPU %d" % (index + 1))


def disk_low_free_space(store, t):
    warn = t["disk_warn_percent"]
    worst = None
    for volume in store[-1]["volumes"]:
        if volume["kind"] not in ("fixed", "removable"):
            continue
        percent = volume["percent"]
        if percent is None or percent < warn:
            continue
        letter = volume["letter"]

        def holds(sample, letter=letter):
            found = volume_of(sample, letter)
            return found is not None and found["percent"] is not None and found["percent"] >= warn

        if held_for(store, t["disk_sustained_ms"], holds) is None:
            continue
        if worst is None or percent > worst[1]:
            worst = (letter, percent)
    if worst is None:
        return None
    letter, percent = worst
    severity = "Critical" if percent >= t["disk_critical_percent"] else "Warning"
    return ("disk.low_free_space", severity, letter)


def disk_filling_fast(store, t):
    window = t["disk_fill_window_ms"]
    if store[-1]["monotonic_ms"] - store[0]["monotonic_ms"] < window:
        return None
    start = store[-1]["monotonic_ms"] - window
    first = next((s for s in store if s["monotonic_ms"] >= start), None)
    if first is None:
        return None
    worst = None
    for volume in store[-1]["volumes"]:
        if volume["kind"] not in ("fixed", "removable") or volume["free"] is None:
            continue
        earlier = volume_of(first, volume["letter"])
        if earlier is None or earlier["free"] is None:
            continue
        lost = max(0, earlier["free"] - volume["free"])
        if lost < t["disk_fill_bytes"]:
            continue
        if worst is None or lost > worst[1]:
            worst = (volume["letter"], lost)
    if worst is None:
        return None
    return ("disk.filling_fast", "Notice", worst[0])


def memory_pressure(store, t):
    warn = t["memory_warn_percent"]
    if store[-1]["memory_percent"] < warn:
        return None
    if held_for(store, t["memory_sustained_ms"], lambda s: s["memory_percent"] >= warn) is None:
        return None
    return ("memory.pressure", "Notice", "system")


def memory_commit_pressure(store, t):
    warn = t["memory_commit_warn_percent"]
    value = store[-1]["commit_percent"]
    if value is None or value < warn:
        return None

    def holds(sample):
        percent = sample["commit_percent"]
        return percent is not None and percent >= warn

    if held_for(store, t["memory_commit_sustained_ms"], holds) is None:
        return None
    return ("memory.commit_pressure", "Warning", "system")


def process_runaway_cpu(store, t):
    warn = t["process_cpu_percent"]
    worst = None
    for process in store[-1]["processes"]:
        if process["cpu"] < warn:
            continue
        pid, created = process["pid"], process["created"]

        def holds(sample, pid=pid, created=created):
            return any(
                c["pid"] == pid and c["created"] == created and c["cpu"] >= warn
                for c in sample["processes"]
            )

        if held_for(store, t["process_cpu_sustained_ms"], holds) is None:
            continue
        if worst is None or process["cpu"] > worst[1]:
            worst = (process, process["cpu"])
    if worst is None:
        return None
    process, _ = worst
    return ("process.runaway_cpu", "Notice", "%s (%d)" % (process["name"], process["pid"]))


def process_memory_growth(store, t):
    window = t["process_growth_window_ms"]
    if store[-1]["monotonic_ms"] - store[0]["monotonic_ms"] < window:
        return None
    start = store[-1]["monotonic_ms"] - window
    first = next((s for s in store if s["monotonic_ms"] >= start), None)
    if first is None:
        return None
    worst = None
    for process in store[-1]["processes"]:
        before = next(
            (
                c["working_set"]
                for c in first["processes"]
                if c["pid"] == process["pid"] and c["created"] == process["created"]
            ),
            None,
        )
        if before is None:
            continue
        grown = max(0, process["working_set"] - before)
        if grown < t["process_growth_bytes"]:
            continue
        if worst is None or grown > worst[1]:
            worst = (process, grown)
    if worst is None:
        return None
    process, _ = worst
    return ("process.memory_growth", "Notice", "%s (%d)" % (process["name"], process["pid"]))


def disk_slow_transfers(store, t):
    slow = t["disk_slow_transfer_seconds"]
    seconds = store[-1]["seconds_per_transfer"]
    if seconds is None or seconds <= 0 or seconds < slow:
        return None

    def holds(sample):
        value = sample["seconds_per_transfer"]
        return value is not None and value >= slow

    if held_for(store, t["disk_slow_sustained_ms"], holds) is None:
        return None
    return ("disk.slow_transfers", "Warning", "system")


def memory_paging(store, t):
    busy = t["memory_pages_per_second"]
    pages = store[-1]["pages"]
    if pages is None or pages <= 0 or pages < busy:
        return None

    def holds(sample):
        value = sample["pages"]
        return value is not None and value >= busy

    if held_for(store, t["memory_paging_sustained_ms"], holds) is None:
        return None
    return ("memory.paging", "Warning", "system")


def system_long_uptime(store, t):
    if store[-1]["uptime"] < t["uptime_long_seconds"]:
        return None
    return ("system.long_uptime", "Info", "system")


RULES = [
    cpu_sustained_high,
    cpu_one_core_pinned,
    disk_low_free_space,
    disk_filling_fast,
    gpu_vram_pressure,
    memory_pressure,
    memory_commit_pressure,
    process_runaway_cpu,
    process_memory_growth,
    disk_slow_transfers,
    memory_paging,
    system_long_uptime,
]


# The keys the Rust structs accept. `deny_unknown_fields` is on every one of them,
# so a misspelled key is not a default: it is a fixture the test harness refuses to
# read. That failure only appears under `cargo test`, which is why this file -
# which has to run without a compiler - checks the names too.
KEYS = {
    "scenario": {"name", "about", "segments", "expect", "quiets"},
    "segment": {
        "minutes", "cpu_percent", "memory_percent", "commit_percent", "volumes", "gpus",
        "uptime_days", "disk_seconds_per_transfer", "pages_input_per_second", "processes",
        "cores",
    },
    "volume": {"letter", "kind", "percent_used"},
    "gpu": {"instance", "used_mb", "limit_mb"},
    "process": {"pid", "name", "cpu_percent", "working_set_mb", "created"},
    "expect": {"rule", "severity", "subject"},
}


def unknown_keys(where, payload, kind):
    extra = set(payload) - KEYS[kind]
    return [f"{where}: {sorted(extra)} are not a {kind}'s keys"] if extra else []


def check_scenarios():
    failures, names = [], []
    fired = {name: 0 for name in REQUIRES}
    quiet = {name: 0 for name in REQUIRES}
    for path in sorted(SCENARIOS.glob("*.json")):
        scenario = json.loads(path.read_text())
        names.append(scenario["name"])
        failures.extend(unknown_keys(path.name, scenario, "scenario"))
        for index, segment in enumerate(scenario["segments"]):
            where = f"{path.name}[{index}]"
            failures.extend(unknown_keys(where, segment, "segment"))
            for volume in segment.get("volumes", []):
                failures.extend(unknown_keys(where, volume, "volume"))
            for gpu in segment.get("gpus", []):
                failures.extend(unknown_keys(where, gpu, "gpu"))
            for process in segment.get("processes", []):
                failures.extend(unknown_keys(where, process, "process"))
        for expected in scenario.get("expect", []):
            failures.extend(unknown_keys(path.name, expected, "expect"))
        store = samples_of(scenario)
        actual = {f for f in (rule(store, DEFAULTS) for rule in RULES) if f}
        expected = {(w["rule"], w["severity"], w["subject"]) for w in scenario.get("expect", [])}
        if actual != expected:
            failures.append(f"{path.name}: expected {sorted(expected)} got {sorted(actual)}")
        for name in scenario.get("quiets", []):
            if any(f[0] == name for f in actual):
                failures.append(f"{path.name}: {name} fired but must stay quiet")
            quiet[name] += 1
        for name in {f[0] for f in actual}:
            fired[name] += 1
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        failures.append(f"duplicate fixture names: {duplicates}")
    for name, count in fired.items():
        if count == 0:
            failures.append(f"{name} never fires in any fixture")
    for name, count in quiet.items():
        if count == 0:
            failures.append(f"{name} is never proven quiet")
    return failures, len(names)


def duration_ms(text):
    return int(text[:-1]) * {"s": 1000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}[text[-1]]


def apply(rule_id, entry, limits):
    if rule_id == "cpu.sustained_high":
        limits["cpu_warn_percent"] = float(entry["warn_percent"])
        limits["cpu_sustained_ms"] = duration_ms(entry["sustained"])
    elif rule_id == "cpu.one_core_pinned":
        limits["core_pinned_percent"] = float(entry["warn_percent"])
        limits["core_pinned_total_below_percent"] = float(entry["total_below_percent"])
        limits["core_pinned_ms"] = duration_ms(entry["sustained"])
    elif rule_id == "disk.low_free_space":
        limits["disk_warn_percent"] = float(entry["warn_percent"])
        limits["disk_critical_percent"] = float(entry["critical_percent"])
        limits["disk_sustained_ms"] = duration_ms(entry["sustained"])
    elif rule_id == "disk.filling_fast":
        limits["disk_fill_bytes"] = int(entry["fill_mb"]) * MIB
        limits["disk_fill_window_ms"] = duration_ms(entry["sustained"])
    elif rule_id == "gpu.vram_pressure":
        limits["gpu_vram_warn_percent"] = float(entry["warn_percent"])
        limits["gpu_vram_sustained_ms"] = duration_ms(entry["sustained"])
    elif rule_id == "memory.pressure":
        limits["memory_warn_percent"] = float(entry["warn_percent"])
        limits["memory_sustained_ms"] = duration_ms(entry["sustained"])
    elif rule_id == "memory.commit_pressure":
        limits["memory_commit_warn_percent"] = float(entry["warn_percent"])
        limits["memory_commit_sustained_ms"] = duration_ms(entry["sustained"])
    elif rule_id == "process.runaway_cpu":
        limits["process_cpu_percent"] = float(entry["warn_percent"])
        limits["process_cpu_sustained_ms"] = duration_ms(entry["sustained"])
    elif rule_id == "process.memory_growth":
        limits["process_growth_bytes"] = int(entry["growth_mb"]) * MIB
        limits["process_growth_window_ms"] = duration_ms(entry["sustained"])
    elif rule_id == "disk.slow_transfers":
        limits["disk_slow_transfer_seconds"] = int(entry["slow_ms"]) / 1000.0
        limits["disk_slow_sustained_ms"] = duration_ms(entry["sustained"])
    elif rule_id == "memory.paging":
        limits["memory_pages_per_second"] = float(entry["pages_per_second"])
        limits["memory_paging_sustained_ms"] = duration_ms(entry["sustained"])
    elif rule_id == "system.long_uptime":
        limits["uptime_long_seconds"] = duration_ms(entry["long_after"]) // 1000


def check_files():
    failures = []
    limits = dict(DEFAULTS)
    files = sorted(RULES_DIR.glob("*.toml"))
    if len(files) != len(REQUIRES):
        failures.append(f"{len(files)} rule files for {len(REQUIRES)} rules")
    claimed = {}
    for path in files:
        entries = tomllib.loads(path.read_text()).get("rule", [])
        if len(entries) != 1:
            failures.append(f"{path.name}: {len(entries)} rules in one file")
            continue
        entry = entries[0]
        rule_id = entry["id"]
        if rule_id not in REQUIRES:
            failures.append(f"{path.name}: unknown rule {rule_id}")
            continue
        keys = {
            k
            for k in entry
            if k not in {"id", "severity", "confidence", "requires", "firing", "near_miss"}
        }
        extra = keys - ALLOWED_KEYS[rule_id]
        if extra:
            failures.append(f"{path.name}: {extra} are not {rule_id}'s keys")
        if entry.get("requires") != REQUIRES[rule_id]:
            failures.append(f"{path.name}: requires {entry.get('requires')}")
        if entry.get("severity") != SEVERITY[rule_id].lower():
            failures.append(f"{path.name}: severity {entry.get('severity')}")
        for key in ("firing", "near_miss"):
            name = entry.get(key)
            if name is None:
                failures.append(f"{path.name}: no {key}")
            elif name in claimed:
                failures.append(f"{path.name}: {name} already claimed by {claimed[name]}")
            else:
                claimed[name] = rule_id
        apply(rule_id, entry, limits)
    for field, value in limits.items():
        if value != DEFAULTS[field]:
            failures.append(f"{field} = {value}, not {DEFAULTS[field]}")
    return failures, claimed, limits


if __name__ == "__main__":
    scenario_failures, count = check_scenarios()
    file_failures, claimed, limits = check_files()
    print(f"fixtures: {count}")
    for failure in scenario_failures + file_failures:
        print("FAIL", failure)
    if not scenario_failures and not file_failures:
        print("every fixture produces exactly what it promises")
        print(f"all {len(limits)} threshold fields match the compiled defaults")
        print(f"{len(claimed)} fixtures claimed, none twice")
