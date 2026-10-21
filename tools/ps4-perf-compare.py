#!/usr/bin/env python3
"""Compare PS4SX2 logs from identical gameplay segments on the PS4.

Usage:
  python3 tools/ps4-perf-compare.py baseline.log candidate.log --warmup 30

The log is written to /data/PS4SX2/logs/PCSX2-vm-boot.log.
Run each build on the *same* disc region, save/scene and internal resolution.
Results are observational; they do not prove causation by themselves.
"""
import argparse
import math
import re
import statistics
from pathlib import Path

PAIRS = re.compile(r"\b([a-zA-Z][a-zA-Z0-9_]*)=(-?(?:\d+(?:\.\d*)?|\.\d+))")
METRICS = {
    "Speed_pct": "%",
    "PS2_Hz": "Hz",
    "Game_FPS": "FPS",
    "Frame_ms": "ms",
    "Frame_max_ms": "ms",
    "EE_pct": "%",
    "GS_pct": "%",
    "VU1_pct": "%",
    "GPU_ms": "ms",
}

def load(path: Path, warmup: float):
    records = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "Performance:" not in line:
            continue
        fields = {name: float(value) for name, value in PAIRS.findall(line)}
        if "Speed_pct" not in fields:
            continue
        if fields.get("seconds", 0.0) < warmup:
            continue
        if not math.isfinite(fields["Speed_pct"]):
            continue
        records.append(fields)
    if not records:
        raise ValueError(f"{path}: no valid Performance samples after {warmup}s warmup")
    return records

def percentile(values, percent):
    v = sorted(values)
    index = (len(v) - 1) * percent / 100
    lo = int(index)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (index - lo)

def summarize(records):
    data = {}
    for name in METRICS:
        values = [r[name] for r in records if name in r and math.isfinite(r[name])]
        if values:
            data[name] = {
                "median": statistics.median(values),
                "p10": percentile(values, 10),
                "p90": percentile(values, 90),
            }
    return data

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path, help="Log from cpu-queue-v1 / original build")
    parser.add_argument("candidate", type=Path, help="Log from the experimental build")
    parser.add_argument("--warmup", type=float, default=30,
                        help="Discard the first N seconds (default: 30)")
    args = parser.parse_args()
    try:
        before = load(args.baseline, args.warmup)
        after = load(args.candidate, args.warmup)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    a, b = summarize(before), summarize(after)
    print(f"Baseline: {len(before)} samples | Candidate: {len(after)} samples | warmup: {args.warmup:g}s")
    print(f"{'Metric':18} {'Baseline p50':>13} {'Candidate p50':>15} {'Delta':>12} {'Unit':>5}")
    for key, unit in METRICS.items():
        if key not in a or key not in b:
            continue
        x, y = a[key]["median"], b[key]["median"]
        print(f"{key:18} {x:13.2f} {y:15.2f} {y-x:+12.2f} {unit:>5}")
    if "Speed_pct" in a and "Speed_pct" in b:
        x, y = a["Speed_pct"], b["Speed_pct"]
        print(f"Speed_pct p10: {x['p10']:.2f}% -> {y['p10']:.2f}%")
        print(f"Speed_pct p90: {x['p90']:.2f}% -> {y['p90']:.2f}%")
    print("NOTE: Use identical gameplay sections and test repeated runs.")
    print("CPU % values are per-thread samples; Game_FPS may be a heuristic,")
    print("not the actual internal frame rate for every title.")

if __name__ == "__main__":
    main()
