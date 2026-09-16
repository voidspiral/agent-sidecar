"""Assist notes from local artifacts; job-assist may call an injected OpenCode runner."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agent_sidecar.opencode_assist import (
    _record_job_assist_success,
    note_summary,
    run_opencode_assist,
)
from agent_sidecar.spi import Event
from agent_sidecar.telemetry import load_telemetry

FORBIDDEN_ACTIONS = ("scancel", "scontrol")


def write_node_assist_note(
    run_dir: Path,
    *,
    host: str,
    events: list[Event],
    artifacts: list[Path],
    summary: str | None = None,
) -> Path:
    assist = run_dir / "assist"
    assist.mkdir(parents=True, exist_ok=True)
    suspected = events[0].reason_code if events else "ok"
    note: dict[str, Any] = {
        "host": host,
        "summary": summary or (events[0].message if events else "no anomalies"),
        "suspected_reason": suspected,
        "evidence_paths": [str(p) for p in artifacts],
        "confidence": 0.5 if events else 1.0,
        "actions": [],
    }
    path = assist / f"{host}.json"
    path.write_text(json.dumps(note, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def note_invokes_slurm(note: dict[str, Any]) -> bool:
    blob = json.dumps(note).lower()
    return any(cmd in blob for cmd in FORBIDDEN_ACTIONS) and bool(note.get("actions"))


def write_job_assist_note(
    run_dir: Path,
    *,
    reason_code: str,
    summary: str,
    evidence_paths: list[str],
) -> Path:
    assist = run_dir / "assist"
    assist.mkdir(parents=True, exist_ok=True)
    note: dict[str, Any] = {
        "host": "submit",
        "summary": summary,
        "suspected_reason": reason_code,
        "evidence_paths": list(evidence_paths),
        "confidence": None,
        "actions": [],
    }
    path = assist / "job.json"
    path.write_text(json.dumps(note, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def final_assist_timeout(
    timeout: float | None = None,
    env: dict[str, str] | None = None,
) -> float | None:
    """Post-job OpenCode budget. None means use AGENT_OPENCODE_TIMEOUT (300s)."""
    if timeout is not None:
        return float(timeout)
    raw = (env or os.environ).get("AGENT_OPENCODE_FINAL_TIMEOUT")
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def promote_live_assist(run_dir: Path) -> bool:
    """Copy assist/live.json summary into job.json using telemetry.reason_code."""
    summary = note_summary(run_dir / "assist" / "live.json")
    if not summary:
        return False
    doc = load_telemetry(run_dir)
    _record_job_assist_success(run_dir, doc, summary)
    return True


def run_job_assist(
    run_dir: Path,
    *,
    user_exit: int,
    opencode_runner=None,
    repo_root: Path | None = None,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
    **_ignored,
) -> int:
    if promote_live_assist(run_dir):
        return user_exit
    budget = final_assist_timeout(timeout, env)
    force_llm = budget is not None and budget > 0
    run_dir = Path(run_dir)
    note_path = run_dir / "assist" / "job.json"
    if not force_llm:
        existing = note_summary(note_path)
        if existing:
            doc = load_telemetry(run_dir)
            _record_job_assist_success(run_dir, doc, existing)
            return user_exit
        from agent_sidecar.analysis.resource_hints import write_resource_hints_note

        write_resource_hints_note(run_dir)
        return user_exit
    # Deterministic packs may have already written job.json; clear it so the
    # OpenCode runner does not treat the pack note as a completed model write.
    pack_backup: str | None = None
    if note_path.is_file():
        pack_backup = note_path.read_text(encoding="utf-8")
        note_path.unlink()
    include_analysis = (run_dir / "assist" / "analysis.json").is_file()
    code = run_opencode_assist(
        run_dir,
        user_exit=user_exit,
        opencode_runner=opencode_runner,
        repo_root=repo_root,
        timeout=budget,
        env=env,
        include_analysis=include_analysis,
    )
    if pack_backup and not note_summary(note_path):
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(pack_backup, encoding="utf-8")
        doc = load_telemetry(run_dir)
        _record_job_assist_success(run_dir, doc, note_summary(note_path))
    return code
