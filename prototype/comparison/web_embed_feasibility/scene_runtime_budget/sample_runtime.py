#!/usr/bin/env python3
"""Sample a standalone 360x320 WKWebView scene without claiming private WebKit ownership."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import statistics
import struct
import subprocess
import threading
import time
from pathlib import Path
from queue import Empty, Queue


HERE = Path(__file__).resolve().parent
DEFAULT_URL = "http://127.0.0.1:8833/?demo=planned_evening"
PS_COLUMNS = ["pid=", "ppid=", "time=", "%cpu=", "rss=", "comm="]


def cpu_seconds(value: str) -> float:
    """Parse macOS ps accumulated CPU time, usually M:SS.CS."""
    days = 0
    if "-" in value:
        day_text, value = value.split("-", 1)
        days = int(day_text)
    fields = value.split(":")
    total = 0.0
    for field in fields:
        total = total * 60 + float(field)
    return days * 86400.0 + total


def processes() -> dict[int, dict]:
    """Accumulated time supports interval CPU; ps %CPU is only a decaying diagnostic."""
    output = subprocess.check_output(["ps", "-A", "-o", ",".join(PS_COLUMNS)], text=True)
    result = {}
    for line in output.splitlines():
        fields = line.strip().split(None, 5)
        if len(fields) != 6:
            continue
        try:
            pid, ppid = int(fields[0]), int(fields[1])
            elapsed_cpu, cpu, rss = cpu_seconds(fields[2]), float(fields[3]), int(fields[4])
        except ValueError:
            continue
        command = fields[5]
        if "com.apple.WebKit.WebContent" in command:
            kind = "web_content"
        elif "com.apple.WebKit.GPU" in command:
            kind = "web_gpu"
        elif "com.apple.WebKit.Networking" in command:
            kind = "web_network"
        else:
            kind = "other"
        result[pid] = {"pid": pid, "ppid": ppid, "cpu_seconds_total": elapsed_cpu,
                       "ps_decaying_cpu_percent": cpu, "rss_kib": rss, "kind": kind}
    return result


def reader(pipe, queue: Queue[str]) -> None:
    for line in pipe:
        queue.put(line.rstrip("\n"))


def instrument_control() -> dict:
    """Known CPU burner catches a broken ps parser or percentage column."""
    command = subprocess.Popen(["/usr/bin/yes"], stdout=subprocess.DEVNULL)
    try:
        before = processes().get(command.pid)
        time.sleep(1.5)
        observed = processes().get(command.pid)
    finally:
        command.terminate()
        command.wait(timeout=5)
    return {
        "kind": "known_cpu_burner",
        "cpu_seconds_delta": round(observed["cpu_seconds_total"] - before["cpu_seconds_total"], 2) if before and observed else None,
        "observed_rss_kib": observed["rss_kib"] if observed else None,
        "parser_detected": before is not None and observed is not None
        and observed["cpu_seconds_total"] - before["cpu_seconds_total"] > 0.5,
    }


def median(values):
    return round(statistics.median(values), 2) if values else None


def strip_png_metadata(path: Path) -> None:
    """Keep lossless image chunks and drop EXIF/other ancillary metadata before publishing."""
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"not a PNG: {path}")
    clean = bytearray(data[:8])
    cursor = 8
    ended = False
    while cursor < len(data):
        length = struct.unpack(">I", data[cursor:cursor + 4])[0]
        end = cursor + 12 + length
        if end > len(data):
            raise ValueError(f"truncated PNG: {path}")
        kind = data[cursor + 4:cursor + 8]
        if kind in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
            clean.extend(data[cursor:end])
        cursor = end
        if kind == b"IEND":
            ended = True
            break
    if not ended:
        raise ValueError(f"missing PNG end: {path}")
    path.write_bytes(clean)


def interval_cpu_percent(items: list[dict], pids: set[int]) -> float | None:
    if len(items) < 2:
        return None
    first, last = items[0], items[-1]
    duration = last["time"] - first["time"]
    if duration <= 0:
        return None
    # Ignore a PID if it is missing at either boundary. The stable-PID list is reported.
    initial = {p["pid"]: p["cpu_seconds_total"] for p in ([first["host"]] if first["host"] else []) + first["webkit"]}
    final = {p["pid"]: p["cpu_seconds_total"] for p in ([last["host"]] if last["host"] else []) + last["webkit"]}
    stable = pids & initial.keys() & final.keys()
    return round(100 * sum(final[pid] - initial[pid] for pid in stable) / duration, 2)


def summarise(samples: list[dict], events: list[dict], baseline_webkit: set[int], control: dict) -> dict:
    event_times = {item["kind"]: item["time"] for item in events if item["kind"] in {"ready", "hidden", "restored", "completed"}}
    webkit_seen = {proc["pid"] for sample in samples for proc in sample["webkit"]}
    new_webkit = sorted(webkit_seen - baseline_webkit)
    first_seen = {pid: next(s["time"] for s in samples if any(p["pid"] == pid for p in s["webkit"])) for pid in new_webkit}
    launched_at = next((e["time"] for e in events if e["kind"] == "launched"), samples[0]["time"])
    launch_cohort = sorted(pid for pid in new_webkit if first_seen[pid] - launched_at <= 5)
    # Transition seconds and initial loading are excluded. WebKit IDs are temporal candidates only.
    bounds = {
        "visible_idle": (event_times.get("ready", float("inf")) + 10, event_times.get("hidden", float("-inf"))),
        "hidden": (event_times.get("hidden", float("inf")) + 5, event_times.get("restored", float("-inf"))),
        "restored": (event_times.get("restored", float("inf")) + 5, event_times.get("completed", float("-inf"))),
    }
    phase_summary = {}
    for phase, (start, end) in bounds.items():
        items = [s for s in samples if start <= s["time"] < end]
        phase_summary[phase] = {
            "count": len(items),
            "host_cpu_core_percent_from_cputime": interval_cpu_percent(items, {items[0]["host"]["pid"]}) if items and items[0]["host"] else None,
            "host_rss_kib_median": median([s["host"]["rss_kib"] for s in items if s["host"]]),
            "launch_cohort_webkit_cpu_core_percent_from_cputime": interval_cpu_percent(items, set(launch_cohort)),
            "launch_cohort_webkit_rss_kib_sum_median": median([
                sum(p["rss_kib"] for p in s["webkit"] if p["pid"] in launch_cohort) for s in items
            ]),
        }
    return {
        "instrument_control": control,
        "baseline_webkit_count": len(baseline_webkit),
        "new_webkit_candidate_pids": new_webkit,
        "new_webkit_first_seen_seconds_after_launch": {str(pid): round(first_seen[pid] - launched_at, 2) for pid in new_webkit},
        "launch_cohort_candidate_pids": launch_cohort,
        "phase_summary": phase_summary,
        "event_kinds": [e["kind"] for e in events],
        "caveat": "Launch cohort means new WebKit PIDs first seen within five seconds of host launch. This is temporal association, not proven ownership: macOS reparents WebKit XPC services to launchd and may reuse services. Later WebKit launches are excluded. Summed RSS double-counts shared pages. CPU interval rates use accumulated ps time; ps %CPU is a decaying average and only retained in raw records. No energy or GPU-power claim.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out", type=Path, default=HERE / "evidence")
    parser.add_argument("--swiftc", default="swiftc")
    parser.add_argument("--kind", choices=("godot", "pixel"), default="godot")
    parser.add_argument("--switch-fixture-on-hidden", action="store_true",
                        help="For a dedicated Godot behavior run on port 8835: switch a fictional fixture after hiding")
    args = parser.parse_args()
    if args.switch_fixture_on_hidden and args.kind != "godot":
        parser.error("fixture switching is only supported for the Godot scene")
    args.out.mkdir(parents=True, exist_ok=True)
    runtime = HERE / "_runtime"
    runtime.mkdir(exist_ok=True)
    fixture = runtime / "switch_fixture.json"
    if args.switch_fixture_on_hidden:
        fixture.write_text(json.dumps({"scene": {"phase": "evening", "mode": "idle", "activity_state": "planned"}}))
    executable = runtime / "WKRoomBudgetProbe"
    subprocess.run([args.swiftc, "-framework", "AppKit", "-framework", "WebKit", str(HERE / "WKRoomBudgetProbe.swift"), "-o", str(executable)], check=True)
    control = instrument_control()
    if not control["parser_detected"]:
        raise SystemExit(f"ps control failed: {control}")
    baseline = processes()
    baseline_webkit = {pid for pid, p in baseline.items() if p["kind"].startswith("web_")}
    proc = subprocess.Popen([str(executable), args.url, str(args.out), args.kind], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    assert proc.stdout is not None
    queue: Queue[str] = Queue()
    thread = threading.Thread(target=reader, args=(proc.stdout, queue), daemon=True)
    thread.start()
    events: list[dict] = []
    samples: list[dict] = []
    started = time.time()
    switched = False
    try:
        while proc.poll() is None and time.time() - started < 130:
            current = time.time()
            while True:
                try:
                    line = queue.get_nowait()
                except Empty:
                    break
                event_match = re.match(r"event time=([0-9.]+) kind=([a-z_]+)", line)
                kind = event_match.group(2) if event_match else "stdout"
                events.append({"time": float(event_match.group(1)) if event_match else current,
                               "kind": kind, "line": line})
                if kind == "hidden" and args.switch_fixture_on_hidden and not switched:
                    fixture.write_text(json.dumps({"scene": {"phase": "day", "mode": "study",
                                                             "activity_state": "declared_active"}}))
                    switched = True
                    events.append({"time": time.time(), "kind": "fixture_switch",
                                   "line": "fictional fixture evening/idle/planned -> day/study/declared_active"})
            snapshot = processes()
            samples.append({
                "time": current,
                "host": snapshot.get(proc.pid),
                "webkit": [p for p in snapshot.values() if p["kind"].startswith("web_")],
            })
            time.sleep(max(0, 1 - (time.time() - current)))
        if proc.poll() is None:
            proc.terminate()
        exit_code = proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
        thread.join(timeout=2)
    while True:
        try:
            line = queue.get_nowait()
        except Empty:
            break
        match = re.match(r"event time=([0-9.]+) kind=([a-z_]+)", line)
        events.append({"time": float(match.group(1)) if match else time.time(),
                       "kind": match.group(2) if match else "stdout", "line": line})
    summary = summarise(samples, events, baseline_webkit, control)
    time.sleep(2)
    after_exit = processes()
    summary["launch_cohort_still_alive_two_seconds_after_host_exit"] = [
        pid for pid in summary["launch_cohort_candidate_pids"] if pid in after_exit
    ]
    summary["exit_code"] = exit_code
    summary["host_pid"] = proc.pid
    summary["scene_kind"] = args.kind
    summary["fictional_fixture_switched_on_hide"] = switched
    summary["system"] = {"macos": platform.mac_ver()[0], "machine": platform.machine(),
                         "logical_cpus": subprocess.check_output(["sysctl", "-n", "hw.logicalcpu"], text=True).strip()}
    summary["url_kind"] = "loopback fictional fixture" if args.url.startswith("http://127.0.0.1:") else "other"
    for name in ("visible-initial.png", "restored.png"):
        file = args.out / name
        if file.is_file():
            strip_png_metadata(file)
        summary.setdefault("screenshots", {})[name] = {
            "exists": file.is_file(),
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None,
        }
    (args.out / "samples.jsonl").write_text("".join(json.dumps(s, sort_keys=True) + "\n" for s in samples))
    (args.out / "events.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events))
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if exit_code != 0 or any(v["count"] < 8 for v in summary["phase_summary"].values()) or "completed" not in summary["event_kinds"]:
        raise SystemExit("Incomplete sample; inspect event log")


if __name__ == "__main__":
    main()
