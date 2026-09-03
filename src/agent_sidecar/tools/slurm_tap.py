"""Parse scontrol/sstat/sacct text into job accounting fields."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from agent_sidecar.classify import SUCCESS_STATES, classify_slurm_state
from agent_sidecar.spi import Event, JobContext

CollectFn = Callable[[str], tuple[str, str]]


def parse_scontrol(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("JobId", "JobState", "NodeList", "ExitCode"):
        m = re.search(rf"{key}=(\S+)", text)
        if m:
            out[key] = m.group(1)
    return out


def _sacct_rows(text: str) -> list[dict[str, Any]]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        rec = parse_scontrol(text)
        return [rec] if rec else []
    header = [h.strip() for h in lines[0].split("|")]
    rows: list[dict[str, Any]] = []
    for line in lines[1:]:
        parts = line.split("|")
        rec = {h: (parts[i].strip() if i < len(parts) else "") for i, h in enumerate(header)}
        if any(rec.values()):
            rows.append(rec)
    return rows


def pick_sacct_record(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Prefer a classified step/job failure over a still-RUNNING allocation row."""
    if not rows:
        return {}
    for rec in rows:
        state = str(rec.get("State") or rec.get("JobState") or "")
        if classify_slurm_state(state):
            return rec
    steps = [
        rec
        for rec in rows
        if "." in str(rec.get("JobID") or rec.get("JobId") or "")
    ]
    if steps:
        return steps[-1]
    return rows[0]


def parse_sacct(text: str) -> dict[str, Any]:
    """Parse `sacct -P` (header + one or more rows)."""
    return pick_sacct_record(_sacct_rows(text))


def merge_job_snapshot(scontrol_rec: dict[str, Any], sacct_rec: dict[str, Any]) -> dict[str, Any]:
    """Keep allocation RUNNING from scontrol from hiding a terminal/failed step."""
    out = dict(scontrol_rec)
    if sacct_rec:
        out.update({k: v for k, v in sacct_rec.items() if v})
    alloc = str(scontrol_rec.get("JobState") or "")
    step = str(sacct_rec.get("State") or sacct_rec.get("JobState") or "")
    step0 = step.split()[0] if step.strip() else ""
    alloc0 = alloc.upper().split()[0] if alloc.strip() else ""
    if classify_slurm_state(step0):
        if alloc:
            out["AllocState"] = alloc
        out["JobState"] = step0
    elif alloc0 in SUCCESS_STATES and step0 and step0.upper() != alloc0:
        out["AllocState"] = alloc
        out["JobState"] = step0
    return out


def _run_cmd(argv: list[str], timeout: float = 5.0) -> str:
    if shutil.which(argv[0]) is None:
        return ""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout or ""


def default_slurm_collect(job_id: str) -> tuple[str, str]:
    jid = str(job_id)
    scontrol = _run_cmd(["scontrol", "show", "job", jid])
    sacct = _run_cmd(["sacct", "-j", jid, "-P", "-o", "JobID,State,ExitCode,MaxRSS"])
    return scontrol, sacct


class SlurmTap:
    name = "slurm-tap"

    def __init__(
        self,
        scontrol_text: str | None = None,
        sacct_text: str | None = None,
        collect: CollectFn | None = None,
    ) -> None:
        self._scontrol = scontrol_text
        self._sacct = sacct_text
        self._collect = collect or default_slurm_collect
        self._injected = scontrol_text is not None or sacct_text is not None
        self._events: list[Event] = []
        self._artifacts: list[Path] = []
        self._ctx: JobContext | None = None

    def start(self, ctx: JobContext) -> None:
        self._ctx = ctx
        self._apply(ctx, *self._texts(ctx.job_id))

    def _texts(self, job_id: str) -> tuple[str, str]:
        if self._injected:
            return self._scontrol or "", self._sacct or ""
        try:
            return self._collect(str(job_id))
        except Exception:
            return "", ""

    def _apply(self, ctx: JobContext, scontrol_text: str, sacct_text: str) -> None:
        scontrol_rec = parse_scontrol(scontrol_text) if scontrol_text else {}
        sacct_rec = parse_sacct(sacct_text) if sacct_text else {}
        parsed = merge_job_snapshot(scontrol_rec, sacct_rec)
        snap = ctx.output_dir / "events" / "slurm.json"
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")
        self._artifacts = [snap]
        state = str(parsed.get("JobState") or parsed.get("State") or "")
        code = classify_slurm_state(state)
        if code:
            self._events = [
                Event(reason_code=code, message=state, evidence_path=str(snap), host=ctx.host)
            ]
        else:
            self._events = []
        if not parsed and not self._injected:
            err = ctx.output_dir / "events" / "slurm_tap.err"
            err.write_text("scontrol produced no job snapshot\n", encoding="utf-8")

    def events(self) -> list[Event]:
        return list(self._events)

    def stop(self) -> None:
        if self._ctx is None or self._injected:
            return
        self._apply(self._ctx, *self._texts(self._ctx.job_id))

    def artifacts(self) -> list[Path]:
        return list(self._artifacts)


def refresh_slurm_snapshot(
    run_dir: Path,
    job_id: str,
    collect: CollectFn | None = None,
) -> None:
    """Submit-host refresh after the user step; skips empty job ids unless collect is injected."""
    jid = str(job_id or "").strip() or "0"
    if collect is None and jid == "0":
        return
    tool = SlurmTap(collect=collect)
    ctx = JobContext(job_id=jid, host="submit", output_dir=run_dir)
    tool.start(ctx)
