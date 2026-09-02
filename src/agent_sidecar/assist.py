"""Assist notes from local artifacts; job-assist may call an injected OpenCode runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_sidecar.opencode_assist import run_opencode_assist
from agent_sidecar.spi import Event

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
    path.write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8")
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
    path.write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8")
    return path


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
    return run_opencode_assist(
        run_dir,
        user_exit=user_exit,
        opencode_runner=opencode_runner,
        repo_root=repo_root,
        timeout=timeout,
        env=env,
    )
