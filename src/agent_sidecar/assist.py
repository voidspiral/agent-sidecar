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
    if budget is not None and budget <= 0:
        return user_exit
    return run_opencode_assist(
        run_dir,
        user_exit=user_exit,
        opencode_runner=opencode_runner,
        repo_root=repo_root,
        timeout=budget,
        env=env,
    )
