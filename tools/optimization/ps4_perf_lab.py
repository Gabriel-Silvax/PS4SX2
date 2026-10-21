#!/usr/bin/env python3
"""Read-only profiling assistant for the experimental PS4SX2 port.

Supports collecting existing PS4 log files over FTP and comparing reproducible
benchmarks. It does not alter the emulator, game timing, or the PS4 filesystem.
Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from ftplib import FTP, all_errors
import json
import math
from pathlib import Path
import re
import statistics
import sys

PERFORMANCE = re.compile(r"\bPerformance:\s*(.*)")
PAIR = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)=(-?(?:\d+(?:\.\d*)?|\.\d+))")
MEASURES = (
    "Speed_pct", "PS2_Hz", "Game_FPS", "Frame_ms", "Frame_max_ms",
    "EE_ms", "GS_ms", "VU1_ms", "GPU_ms", "EE_pct", "GS_pct", "VU1_pct"
)
BUDGET_NTSC_MS = 1000 / (60000 / 1001)  # 59.94 Hz, illustrative frame budget.
DEFAULT_REMOTE_LOG = "/data/PS4SX2/logs/PCSX2-vm-boot.log"


def parse_samples(text: str, warmup: float = 30.0) -> list[dict[str, float]]:
    """Extract timestamped performance rows emitted by HostVM.cpp."""
    if warmup < 0:
        raise ValueError("warmup must be >= 0")
    samples: list[dict[str, float]] = []
    for line in text.splitlines():
        match = PERFORMANCE.search(line)
        if not match:
            continue
        row = {key: float(value) for key, value in PAIR.findall(match.group(1))}
        elapsed = row.get("seconds")
        speed = row.get("Speed_pct")
        if elapsed is None or not math.isfinite(elapsed) or elapsed < warmup:
            continue
        if speed is None or not math.isfinite(speed):
            continue
        row = {key: value for key, value in row.items() if math.isfinite(value)}
        samples.append(row)
    return samples


def quantile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    k = (len(ordered) - 1) * percentile / 100
    lo = math.floor(k)
    hi = math.ceil(k)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def summarize(samples: list[dict[str, float]]) -> dict:
    if not samples:
        raise ValueError("nenhuma linha Performance válida; confira o log e --warmup")
    metrics = {}
    for name in MEASURES:
        values = [row[name] for row in samples if name in row]
        if values:
            metrics[name] = {
                "median": round(statistics.median(values), 3),
                "p10": round(quantile(values, 10), 3),
                "p90": round(quantile(values, 90), 3),
            }
    component = {name: metrics[name]["median"] for name in ("EE_ms", "GS_ms", "VU1_ms") if name in metrics}
    dominant = max(component, key=component.get) if component else None
    earliest = min(row["seconds"] for row in samples)
    latest = max(row["seconds"] for row in samples)
    flags = []
    if len(samples) < 8:
        flags.append("Poucas amostras; faça um teste maior para comparar com confiança.")
    if latest - earliest < 30:
        flags.append("Janela observada inferior a 30 segundos.")
    if not component:
        flags.append("Sem tempos EE/GS/VU1 neste log; análise do gargalo indisponível.")
    if "Game_FPS" in metrics:
        flags.append("Game_FPS depende da heurística de FPS interno; não é FPS real garantido.")
    return {
        "sample_count": len(samples),
        "seconds_from": earliest,
        "seconds_to": latest,
        "metrics": metrics,
        "dominant_component_by_median": dominant,
        "budget_ntsc_ms": round(BUDGET_NTSC_MS, 3),
        "over_budget_components": [name for name, value in component.items() if value > BUDGET_NTSC_MS],
        "warnings": flags,
    }


def load_summary(path: Path, warmup: float) -> dict:
    content = path.read_text(encoding="utf-8", errors="replace")
    return summarize(parse_samples(content, warmup))


def print_summary(title: str, report: dict) -> None:
    print(f"{title}: {report['sample_count']} amostras | "
          f"{report['seconds_from']:.1f}–{report['seconds_to']:.1f} s")
    for key in MEASURES:
        stat = report["metrics"].get(key)
        if stat:
            suffix = "%" if key.endswith("pct") else ("ms" if key.endswith("_ms") else "")
            print(f"  {key:<14} p10 {stat['p10']:>8.2f} | mediana {stat['median']:>8.2f} | p90 {stat['p90']:>8.2f} {suffix}")
    print(f"  Maior tempo mediano: {report['dominant_component_by_median'] or 'indisponível'}")
    for warning in report["warnings"]:
        print(f"  Atenção: {warning}")


def ftp_fetch(host: str, port: int, user: str, password: str,
              remote_path: str, target: Path, timeout: float) -> None:
    if target.exists():
        raise FileExistsError(f"arquivo de saída já existe: {target} (escolha outro nome)")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".partial")
    if tmp.exists():
        raise FileExistsError(f"arquivo temporário já existe: {tmp}")
    try:
        with FTP() as ftp:
            ftp.connect(host, port, timeout=timeout)
            ftp.login(user=user, passwd=password)
            with tmp.open("wb") as sink:
                ftp.retrbinary(f"RETR {remote_path}", sink.write)
        tmp.replace(target)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def save_json(filename: Path | None, obj: dict) -> None:
    if filename is not None:
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Relatório JSON: {filename}")


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="command", required=True)
    capture = modes.add_parser("fetch", help="Baixar log existente do PS4 via FTP (somente leitura)")
    capture.add_argument("--host", required=True, help="IP local do PS4")
    capture.add_argument("--port", type=int, default=2121, help="Porta do servidor FTP (padrão: 2121)")
    capture.add_argument("--user", default="anonymous")
    capture.add_argument("--password", default="anonymous@")
    capture.add_argument("--remote-path", default=DEFAULT_REMOTE_LOG)
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--timeout", type=float, default=20.0)

    analyze = modes.add_parser("analyze", help="Analisar amostras de um log")
    analyze.add_argument("log", type=Path)
    analyze.add_argument("--warmup", type=float, default=30.0)
    analyze.add_argument("--json", type=Path, help="Salvar relatório JSON")

    compare = modes.add_parser("compare", help="Comparar baseline e versão experimental")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("candidate", type=Path)
    compare.add_argument("--warmup", type=float, default=30.0)
    compare.add_argument("--json", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "fetch":
            ftp_fetch(args.host, args.port, args.user, args.password, args.remote_path, args.output, args.timeout)
            print(f"Log salvo: {args.output}")
        elif args.command == "analyze":
            report = load_summary(args.log, args.warmup)
            print_summary(args.log.name, report)
            save_json(args.json, {"source": str(args.log), "warmup_seconds": args.warmup, **report})
        elif args.command == "compare":
            a = load_summary(args.baseline, args.warmup)
            b = load_summary(args.candidate, args.warmup)
            print_summary("Antes", a)
            print_summary("Depois", b)
            print("\nDiferença nas medianas (depois - antes):")
            differences = {}
            for name in MEASURES:
                if name in a["metrics"] and name in b["metrics"]:
                    delta = b["metrics"][name]["median"] - a["metrics"][name]["median"]
                    differences[name] = round(delta, 3)
                    print(f"  {name:<14} {delta:+.2f}")
            print("Validade da comparação: mesmo jogo/região/cena/resolução, sem overlays extras e 3+ repetições.")
            save_json(args.json, {"baseline": a, "candidate": b, "median_deltas": differences,
                                  "warmup_seconds": args.warmup, "created_utc": datetime.now(timezone.utc).isoformat()})
    except (ValueError, *all_errors) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(run())
