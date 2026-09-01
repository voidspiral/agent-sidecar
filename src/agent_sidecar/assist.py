"""Non-model node-assist notes from local artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    run_dir = run_dir
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
