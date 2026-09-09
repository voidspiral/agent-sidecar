"""Route reason_code to a pack name."""

from __future__ import annotations

from typing import Any


def select_pack(reason_code: str, summary: dict[str, Any]) -> str:
    if reason_code == "mpi_abort":
        return "mpi_abort"
    if reason_code == "execution_error" and int(summary.get("pid_count") or 0) == 0:
        return "launch_fail"
    # Deferred stubs (not implemented as full packs in this change).
    if reason_code in {"slurm_oom", "node_local", "node_fail", "io_stall", "cpu_idle"}:
        return "stub"
    return "generic"
