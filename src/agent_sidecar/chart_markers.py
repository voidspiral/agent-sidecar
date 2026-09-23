"""First-seen chart markers for classified point events."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from agent_sidecar.spi import Event

CHART_MARKER_CODES = frozenset(
    {
        "mpi_abort",
        "mpi_segfault",
        "mpi_fpe",
        "mpi_deadlock",
        "slurm_oom",
        "node_local",
    }
)
_HOST_RE = re.compile(r"[^A-Za-z0-9._-]+")


def marker_filename(host: str | None) -> str:
    safe = _HOST_RE.sub("_", (host or "submit").strip()) or "submit"
    if safe == "submit":
        return "submit_markers.jsonl"
    return f"{safe}_markers.jsonl"


def marker_path(run_dir: Path, host: str | None) -> Path:
    return Path(run_dir) / "events" / marker_filename(host)


def relative_evidence_path(run_dir: Path, evidence_path: str | Path | None) -> str:
    if evidence_path is None:
        return ""
    path = Path(evidence_path)
    run_dir = Path(run_dir)
    try:
        if path.is_absolute():
            return str(path.relative_to(run_dir))
    except ValueError:
        return str(path)
    return str(path)


def load_markers(run_dir: Path) -> list[dict[str, Any]]:
    events = Path(run_dir) / "events"
    if not events.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(events.glob("*_markers.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            code = str(rec.get("reason_code") or "")
            if code not in CHART_MARKER_CODES:
                continue
            try:
                ts = float(rec["ts"])
            except (KeyError, TypeError, ValueError):
                continue
            out.append(
                {
                    "ts": ts,
                    "reason_code": code,
                    "message": str(rec.get("message") or ""),
                    "evidence_path": str(rec.get("evidence_path") or ""),
                    "host": str(rec.get("host") or ""),
                }
            )
    return out


def _existing_keys(path: Path) -> set[tuple[str, str, str]]:
    seen: set[tuple[str, str, str]] = set()
    if not path.is_file():
        return seen
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        seen.add(
            (
                str(rec.get("reason_code") or ""),
                str(rec.get("evidence_path") or ""),
                str(rec.get("host") or ""),
            )
        )
    return seen


def record_marker(
    run_dir: Path,
    *,
    reason_code: str,
    host: str | None,
    evidence_path: str | Path | None,
    message: str = "",
    ts: float | None = None,
    now: float | None = None,
) -> bool:
    """Append a first-seen chart marker. Returns True when a new line is written."""
    if reason_code not in CHART_MARKER_CODES:
        return False
    import time

    run_dir = Path(run_dir)
    host_s = (host or "submit").strip() or "submit"
    rel = relative_evidence_path(run_dir, evidence_path)
    stamp = float(ts if ts is not None else (now if now is not None else time.time()))
    dest = marker_path(run_dir, host_s)
    dest.parent.mkdir(parents=True, exist_ok=True)
    key = (reason_code, rel, host_s)
    if key in _existing_keys(dest):
        return False
    rec = {
        "ts": stamp,
        "reason_code": reason_code,
        "message": message,
        "evidence_path": rel,
        "host": host_s,
    }
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    return True


def record_event_marker(run_dir: Path, event: Event, *, now: float | None = None) -> Event:
    """Persist a chart marker for a plugin event and return it with ts set."""
    stamp = event.ts
    if stamp is None:
        import time

        stamp = float(now if now is not None else time.time())
    wrote_ts = stamp
    if event.reason_code in CHART_MARKER_CODES:
        record_marker(
            run_dir,
            reason_code=event.reason_code,
            host=event.host,
            evidence_path=event.evidence_path,
            message=event.message,
            ts=stamp,
        )
    if event.ts is None:
        return Event(
            reason_code=event.reason_code,
            message=event.message,
            evidence_path=event.evidence_path,
            host=event.host,
            ts=wrote_ts,
        )
    return event


def markers_in_range(
    markers: Iterable[dict[str, Any]],
    xs: list[float],
    *,
    pad: float | None = None,
) -> list[dict[str, Any]]:
    samples = [float(x) for x in xs]
    if not samples:
        return []
    lo = min(samples)
    hi = max(samples)
    extra = pad if pad is not None else max(2.0, (hi - lo) * 0.1)
    out: list[dict[str, Any]] = []
    for rec in markers:
        try:
            ts = float(rec["ts"])
        except (KeyError, TypeError, ValueError):
            continue
        if lo <= ts <= hi + extra:
            out.append(rec)
    return out
