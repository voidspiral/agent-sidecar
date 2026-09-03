"""Deterministic SLURM / MPI reason codes."""

from __future__ import annotations

import re

SLURM_STATE_CODES = {
    "OUT_OF_MEMORY": "slurm_oom",
    "OOM": "slurm_oom",
    "NODE_FAIL": "node_fail",
    "TIMEOUT": "timeout",
    "CANCELLED": "cancelled",
    "CANCELED": "cancelled",
}

SUCCESS_STATES = {"COMPLETED", "COMPLETING", "RUNNING", "PENDING", "CONFIGURING"}

MPI_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"MPI_Abort"), "mpi_abort"),
    (re.compile(r"PMIx.*abort", re.IGNORECASE), "mpi_abort"),
    (re.compile(r"assert\s*\(\s*!closed\s*\)"), "mpi_abort"),
    (re.compile(r"disconnected\s+rank", re.IGNORECASE), "mpi_abort"),
]


def classify_slurm_state(state: str) -> str | None:
    raw = (state or "").strip().upper()
    raw = raw.split(" ")[0]
    if not raw:
        return None
    if raw in SLURM_STATE_CODES:
        return SLURM_STATE_CODES[raw]
    if raw in SUCCESS_STATES:
        return None
    if raw in {"FAILED", "DEADLINE", "BOOT_FAIL", "PREEMPTED"}:
        return "slurm_failed"
    return "slurm_failed" if raw not in {"UNKNOWN"} else None


def classify_mpi_text(text: str) -> str | None:
    if not text:
        return None
    for pattern, code in MPI_PATTERNS:
        if pattern.search(text):
            return code
    return None


def classify_mpi_file(path: str | None) -> list[str]:
    if not path:
        return []
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        return []
    code = classify_mpi_text(p.read_text(encoding="utf-8", errors="replace"))
    return [code] if code else []


def classify_node_diag_text(text: str) -> str | None:
    """Return node_local when the snapshot shows a job-scoped OOM or fs hang."""
    if not text:
        return None
    lowered = text.lower()
    if "killed process" in lowered:
        return "node_local"
    if re.search(r"oom_pids=\[[^\]]+", text) and "oom_pids=[]" not in text:
        return "node_local"
    if re.search(r"(?m)^oom_kill=([1-9]\d*)\s*$", text):
        return "node_local"
    if re.search(r"(?m)^fs_hang_lines=([1-9]\d*)\s*$", text):
        return "node_local"
    return None
