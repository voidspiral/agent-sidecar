"""JobTelemetry document and run directory layout."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_sidecar.classify import (
    classify_mpi_text,
    classify_node_diag_text,
    classify_slurm_state,
)


def make_run_id(*, now: datetime | None = None, pid: int = 0) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%SZ") + f"-{pid}"


def ensure_run_layout(run_dir: Path) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "series").mkdir(exist_ok=True)
    (run_dir / "assist").mkdir(exist_ok=True)
    (run_dir / "events").mkdir(exist_ok=True)
    (run_dir / "charts").mkdir(exist_ok=True)
    return run_dir


def retry_metadata(*, user_exit: int | None, overlap_failed_before_start: bool, attempt: int = 1) -> dict[str, Any]:
    if overlap_failed_before_start and (user_exit is None):
        return {"retry_allowed": True, "attempt": attempt}
    return {"retry_allowed": False, "attempt": attempt}


def write_meta(run_dir: Path, data: dict[str, Any]) -> Path:
    ensure_run_layout(run_dir)
    path = run_dir / "meta.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def write_telemetry(
    run_dir: Path,
    *,
    summary: dict[str, Any],
    anomalies: list[dict[str, Any]],
    evidence_paths: list[str],
    reason_code: str,
    retry_allowed: bool,
    attempt: int,
    node_assist: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    ensure_run_layout(run_dir)
    doc: dict[str, Any] = {
        "summary": summary,
        "anomalies": anomalies,
        "evidence_paths": evidence_paths,
        "reason_code": reason_code,
        "retry_allowed": retry_allowed,
        "attempt": attempt,
    }
    if node_assist is not None:
        doc["node_assist"] = node_assist
    if extra:
        doc.update(extra)
    path = run_dir / "telemetry.json"
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def load_telemetry(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "telemetry.json").read_text(encoding="utf-8"))


def summarize_series(run_dir: Path) -> dict[str, Any]:
    series = run_dir / "series"
    files = list(series.glob("*.jsonl")) if series.is_dir() else []
    cpu: list[float] = []
    rss: list[float] = []
    io_r = 0.0
    io_w = 0.0
    eth_rx: list[float] = []
    eth_tx: list[float] = []
    hosts: set[str] = set()
    pids = 0
    for path in files:
        is_net = path.name.endswith("_net.jsonl")
        is_pid = path.name.endswith(".jsonl") and "_pid" in path.name and not is_net
        if is_pid:
            pids += 1
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            hosts.add(str(rec.get("host", "")))
            if "cpu_pct" in rec:
                cpu.append(float(rec["cpu_pct"]))
            if "rss_mb" in rec:
                rss.append(float(rec["rss_mb"]))
            if is_pid or "pid" in rec:
                io_r += float(rec.get("io_read_bps") or 0)
                io_w += float(rec.get("io_write_bps") or 0)
            if is_net or "iface" in rec:
                if rec.get("eth_rx_bps") is not None:
                    eth_rx.append(float(rec["eth_rx_bps"]))
                if rec.get("eth_tx_bps") is not None:
                    eth_tx.append(float(rec["eth_tx_bps"]))
    return {
        "host_count": len(hosts - {""}),
        "pid_count": pids,
        "cpu_avg": (sum(cpu) / len(cpu)) if cpu else None,
        "cpu_peak": max(cpu) if cpu else None,
        "rss_peak_mb": max(rss) if rss else None,
        "io_read_bps_sum": io_r,
        "io_write_bps_sum": io_w,
        "eth_rx_bps_peak": max(eth_rx) if eth_rx else None,
        "eth_tx_bps_peak": max(eth_tx) if eth_tx else None,
    }


def anomalies_from_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    events_dir = run_dir / "events"
    if not events_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(events_dir.iterdir()):
        if not path.is_file():
            continue
        rel = str(path.relative_to(run_dir)) if path.is_relative_to(run_dir) else str(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = {}
            if isinstance(data, dict):
                state = str(data.get("JobState") or data.get("State") or "")
                code = classify_slurm_state(state)
                if code:
                    key = (code, rel)
                    if key not in seen:
                        seen.add(key)
                        out.append(
                            {"reason_code": code, "message": state, "evidence_path": rel}
                        )
        mpi = classify_mpi_text(text)
        if mpi:
            key = (mpi, rel)
            if key not in seen:
                seen.add(key)
                out.append(
                    {
                        "reason_code": mpi,
                        "message": "mpi runtime fault",
                        "evidence_path": rel,
                    }
                )
        if path.name.startswith("node-diag"):
            node = classify_node_diag_text(text)
            if node:
                key = (node, rel)
                if key not in seen:
                    seen.add(key)
                    out.append(
                        {
                            "reason_code": node,
                            "message": "node-local oom",
                            "evidence_path": rel,
                        }
                    )
    return out


def rollup_reason_code(anomalies: list[dict[str, Any]], *, user_exit: int) -> str:
    if anomalies:
        return str(anomalies[0]["reason_code"])
    return "ok" if user_exit == 0 else "execution_error"
