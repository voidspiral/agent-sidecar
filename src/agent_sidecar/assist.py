"""Assist notes from local artifacts; job-assist may call an injected LLM client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_sidecar.llm import LlmConfig, LlmError, chat_complete
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


def _persist_telemetry(run_dir: Path, doc: dict[str, Any]) -> None:
    (run_dir / "telemetry.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )


def run_job_assist(
    run_dir: Path,
    *,
    cfg: LlmConfig,
    user_exit: int,
    transport=None,
) -> int:
    doc = load_telemetry(run_dir)
    errors = dict(doc.get("collect_errors") or {})
    try:
        text, _payload = chat_complete(cfg, doc, transport=transport)
    except LlmError as exc:
        errors[exc.code] = exc.message
        doc["collect_errors"] = errors
        _persist_telemetry(run_dir, doc)
        return user_exit
    reason = str(doc.get("reason_code") or "ok")
    rel = "assist/job.json"
    write_job_assist_note(
        run_dir,
        reason_code=reason,
        summary=text,
        evidence_paths=list(doc.get("evidence_paths") or []),
    )
    evidence = list(doc.get("evidence_paths") or [])
    if rel not in evidence:
        evidence.append(rel)
    doc["evidence_paths"] = evidence
    doc["job_assist"] = [{"path": rel, "host": "submit"}]
    doc["collect_errors"] = errors
    _persist_telemetry(run_dir, doc)
    return user_exit
