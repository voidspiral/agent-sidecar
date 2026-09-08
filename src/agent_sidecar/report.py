"""Human-readable final report from a run directory."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

SERIES_NAME = re.compile(r"^(?P<host>.+)_pid(?P<pid>\d+)\.jsonl$")


def _rel_files(run_dir: Path, folder: str, pattern: str = "*") -> list[str]:
    d = run_dir / folder
    if not d.is_dir():
        return []
    out: list[str] = []
    for path in sorted(d.glob(pattern)):
        if path.is_file():
            out.append(str(path.relative_to(run_dir)))
    return out


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _job_assist_summary(run_dir: Path) -> str:
    note_path = run_dir / "assist" / "job.json"
    if not note_path.is_file():
        return ""
    return str(_load_json(note_path).get("summary") or "").strip()


def _hosts_from_series(run_dir: Path) -> list[tuple[str, list[int]]]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for rel in _rel_files(run_dir, "series", "*.jsonl"):
        matched = SERIES_NAME.match(Path(rel).name)
        if matched is None:
            continue
        grouped[matched.group("host")].append(int(matched.group("pid")))
    return [(host, sorted(set(grouped[host]))) for host in sorted(grouped)]


def _metrics_line(summary: dict[str, Any]) -> str | None:
    parts: list[str] = []
    cpu_avg = summary.get("cpu_avg")
    cpu_peak = summary.get("cpu_peak")
    if cpu_avg is not None and cpu_peak is not None:
        parts.append(f"cpu avg/peak {cpu_avg}/{cpu_peak}")
    elif cpu_avg is not None:
        parts.append(f"cpu_avg {cpu_avg}")
    elif cpu_peak is not None:
        parts.append(f"cpu_peak {cpu_peak}")
    rss = summary.get("rss_peak_mb")
    if rss is not None:
        parts.append(f"rss_peak_mb {rss}")
    io_r = summary.get("io_read_bps_sum")
    io_w = summary.get("io_write_bps_sum")
    if io_r is not None or io_w is not None:
        empty_io = float(io_r or 0) == 0.0 and float(io_w or 0) == 0.0
        if empty_io and cpu_avg is None and cpu_peak is None and rss is None:
            pass
        else:
            read_s = "-" if io_r is None else io_r
            write_s = "-" if io_w is None else io_w
            parts.append(f"io_r/w {read_s}/{write_s}")
    if not parts:
        return None
    return "metrics  " + "  ".join(parts)


def _named_or_count(folder: str, rels: list[str], *, limit: int = 3) -> str:
    if not rels:
        return f"{folder}/×0"
    if len(rels) <= limit:
        names = ",".join(Path(rel).name for rel in rels)
        return f"{folder}/{names}"
    return f"{folder}/×{len(rels)}"


def format_run_report(run_dir: Path) -> str:
    run_dir = Path(run_dir)
    tel = run_dir / "telemetry.json"
    doc = _load_json(tel) if tel.is_file() else {}
    summary = dict(doc.get("summary") or {})
    lines = [
        "======== agent report ========",
        f"run:    {run_dir}",
        (
            f"exit:   {summary.get('exit_code', '')}    "
            f"reason: {doc.get('reason_code', '')}    "
            f"hosts: {summary.get('host_count', '')}    "
            f"pids: {summary.get('pid_count', '')}"
        ),
        "",
    ]
    note = _job_assist_summary(run_dir)
    if note:
        lines.extend(note.splitlines())
        lines.append("")
    metrics = _metrics_line(summary)
    if metrics:
        lines.append(metrics)
        lines.append("")
    grouped = _hosts_from_series(run_dir)
    if grouped:
        lines.append("hosts")
        for host, pids in grouped:
            pid_s = ", ".join(str(pid) for pid in pids)
            lines.append(f"  {host}  pid {pid_s}")
        lines.append("")
    errors = doc.get("collect_errors") or {}
    if errors:
        lines.append("errors")
        for key, val in errors.items():
            lines.append(f"  {key}: {str(val)[:200]}")
        lines.append("")
    series = _rel_files(run_dir, "series", "*.jsonl")
    charts = _rel_files(run_dir, "charts", "*.png")
    events = _rel_files(run_dir, "events")
    assist = _rel_files(run_dir, "assist")
    lines.append(
        "evidence  "
        + "  ".join(
            [
                f"series/×{len(series)}",
                f"charts/×{len(charts)}",
                _named_or_count("events", events),
                _named_or_count("assist", assist),
            ]
        )
    )
    lines.append("========")
    return "\n".join(lines) + "\n"


def write_run_report(run_dir: Path) -> Path:
    path = Path(run_dir) / "report.txt"
    path.write_text(format_run_report(run_dir), encoding="utf-8")
    return path
