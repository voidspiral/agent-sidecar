"""Human-readable final report from a run directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _rel_files(run_dir: Path, folder: str, pattern: str = "*") -> list[str]:
    d = run_dir / folder
    if not d.is_dir():
        return []
    out: list[str] = []
    for path in sorted(d.glob(pattern)):
        if path.is_file():
            out.append(str(path.relative_to(run_dir)))
    return out


def format_run_report(run_dir: Path) -> str:
    run_dir = Path(run_dir)
    lines = [
        "======== agent report ========",
        f"run_dir: {run_dir}",
    ]
    tel = run_dir / "telemetry.json"
    doc: dict[str, Any] = {}
    if tel.is_file():
        try:
            doc = json.loads(tel.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            doc = {}
    summary = dict(doc.get("summary") or {})
    lines.append(f"exit_code: {summary.get('exit_code', '')}")
    lines.append(f"reason_code: {doc.get('reason_code', '')}")
    lines.append("summary:")
    for key in (
        "host_count",
        "pid_count",
        "cpu_avg",
        "cpu_peak",
        "rss_peak_mb",
        "io_read_bps_sum",
        "io_write_bps_sum",
    ):
        if key in summary:
            lines.append(f"  {key}: {summary[key]}")
    errors = doc.get("collect_errors") or {}
    if errors:
        lines.append("collect_errors:")
        for key, val in errors.items():
            lines.append(f"  {key}: {str(val)[:200]}")
    else:
        lines.append("collect_errors: {}")
    artifacts = (
        _rel_files(run_dir, "series", "*.jsonl")
        + _rel_files(run_dir, "charts", "*.png")
        + _rel_files(run_dir, "events")
        + _rel_files(run_dir, "assist")
    )
    meta = run_dir / "meta.json"
    if meta.is_file():
        artifacts.insert(0, "meta.json")
    if tel.is_file():
        artifacts.insert(0, "telemetry.json")
    lines.append("artifacts:")
    if artifacts:
        for rel in artifacts:
            lines.append(f"  {rel}")
    else:
        lines.append("  (none)")
    note_path = run_dir / "assist" / "job.json"
    if note_path.is_file():
        try:
            note = json.loads(note_path.read_text(encoding="utf-8"))
            note_summary = str(note.get("summary") or "").strip()
        except json.JSONDecodeError:
            note_summary = ""
        if note_summary:
            lines.append("job-assist:")
            for row in note_summary.splitlines():
                lines.append(f"  {row}")
    lines.append("========")
    return "\n".join(lines) + "\n"


def write_run_report(run_dir: Path) -> Path:
    path = Path(run_dir) / "report.txt"
    path.write_text(format_run_report(run_dir), encoding="utf-8")
    return path
