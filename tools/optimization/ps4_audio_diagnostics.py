#!/usr/bin/env python3
"""Report SPU2/AudioOut queue health from PS4SX2 logs; read-only.

Example:
 python3 tools/optimization/ps4_audio_diagnostics.py baseline.log recovery.log

'input_short' counts short input reads, which can result from producer
starvation or timing. It does not by itself prove CPU affinity was the cause.
"""
from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from statistics import median

AUDIO = re.compile(r"PS4 audio output:.*?\bstatus=(-?\d+).*?\bbuffers=(\d+).*?\bpcm_buffers=(\d+).*?\binput_short=(\d+)")
QUEUE = re.compile(r"PS4 audio queue:.*?\bmin_frames=(\d+).*?\bmax_frames=(\d+).*?\brefill_pending=(\d+)")
SIGNAL = re.compile(r"PS4 audio signal:.*?\binvalid_samples=(\d+).*?\bclipped_samples=(\d+)")
PERFORMANCE = re.compile(r"\bPerformance:\s*.*?\bSpeed_pct=(-?[\d.]+)")
AFFINITY = re.compile(r"PS4 (?:Jaguar|audio-recovery) affinity: (.*)")
ROLLOVER_FIELDS = ("buffers", "input_short", "pcm_buffers", "refill_pending")


def parse_log(text: str) -> dict:
    """Return counters per session, never sum cumulative counters."""
    sessions = []
    current = {"output": [], "queues": [], "signals": [], "speed": [], "affinity": []}
    # New session restart typically opens a new log; detect a counter reset if logs
    # were appended, since a cumulative counter can restart at zero.
    last_buffers = None
    for line in text.splitlines():
        a = AUDIO.search(line)
        if a:
            status, buffers, pcm, short = map(int, a.groups())
            if last_buffers is not None and buffers < last_buffers and current["output"]:
                sessions.append(current)
                current = {"output": [], "queues": [], "signals": [], "speed": [], "affinity": []}
            last_buffers = buffers
            current["output"].append({"status": status, "buffers": buffers, "pcm_buffers": pcm, "input_short": short})
        b = QUEUE.search(line)
        if b:
            lo, hi, pending = map(int, b.groups())
            current["queues"].append({"min_frames": lo, "max_frames": hi, "refill_pending": pending})
        c = SIGNAL.search(line)
        if c:
            invalid, clipped = map(int, c.groups())
            current["signals"].append({"invalid_samples": invalid, "clipped_samples": clipped})
        d = PERFORMANCE.search(line)
        if d:
            value = float(d.group(1))
            if math.isfinite(value):
                current["speed"].append(value)
        e = AFFINITY.search(line)
        if e:
            current["affinity"].append(e.group(1))
    if any(current.values()):
        sessions.append(current)
    return {"sessions": sessions}


def summarize(session: dict) -> dict:
    outputs = session["output"]
    queues = session["queues"]
    speeds = session["speed"]
    status = outputs[-1]["status"] if outputs else None
    total_buffers = outputs[-1]["buffers"] - outputs[0]["buffers"] if len(outputs) > 1 else None
    total_short = outputs[-1]["input_short"] - outputs[0]["input_short"] if len(outputs) > 1 else None
    if total_buffers is not None and total_buffers <= 0:
        total_buffers = None
        total_short = None
    return {
        "output_status_latest": status,
        "samples": len(outputs),
        "input_short_delta": total_short,
        "buffers_delta": total_buffers,
        "short_input_per_1000_buffers": round(1000 * total_short / total_buffers, 2)
            if total_buffers is not None and total_short is not None and total_short >= 0 else None,
        "min_queue_frames_seen": min((item["min_frames"] for item in queues), default=None),
        "max_queue_frames_seen": max((item["max_frames"] for item in queues), default=None),
        "refill_pending_delta": queues[-1]["refill_pending"] - queues[0]["refill_pending"]
            if len(queues) >= 2 else None,
        "median_speed_pct": round(median(speeds), 2) if speeds else None,
        "affinity_messages": list(dict.fromkeys(session["affinity"])),
        "invalid_samples_latest": session["signals"][-1]["invalid_samples"] if session["signals"] else None,
        "clipped_samples_latest": session["signals"][-1]["clipped_samples"] if session["signals"] else None,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("logs", type=Path, nargs="+", help="PS4SX2 boot logs, in baseline then candidate order")
    args = p.parse_args()
    for log in args.logs:
        try:
            parsed = parse_log(log.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            p.error(str(exc))
        print(f"\n{log} — {len(parsed['sessions'])} session(s)")
        if not parsed["sessions"]:
            print("  No PS4 audio log markers; check correct file and logging configuration.")
        for number, session in enumerate(parsed["sessions"], start=1):
            report = summarize(session)
            print(f"  Session {number}")
            for key, value in report.items():
                print(f"    {key}: {value}")
            if report["short_input_per_1000_buffers"] is None:
                print("    Collect a longer scene for multiple output snapshots.")
            print("    Note: short reads also occur when the emulator cannot produce audio fast enough.")


if __name__ == "__main__":
    main()
