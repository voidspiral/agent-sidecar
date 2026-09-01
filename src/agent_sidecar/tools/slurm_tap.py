"""Parse scontrol/sstat/sacct text into job accounting fields."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agent_sidecar.classify import classify_slurm_state
from agent_sidecar.spi import Event, JobContext


def parse_scontrol(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("JobId", "JobState", "NodeList", "ExitCode"):
        m = re.search(rf"{key}=(\S+)", text)
        if m:
            out[key] = m.group(1)
    return out


def parse_sacct(text: str) -> dict[str, Any]:
    """Parse a simple `sacct -P` snippet (header + row)."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return parse_scontrol(text)
    header = lines[0].split("|")
    row = lines[1].split("|")
    rec = {h.strip(): (row[i].strip() if i < len(row) else "") for i, h in enumerate(header)}
    return rec


class SlurmTap:
    name = "slurm-tap"

    def __init__(self, scontrol_text: str = "", sacct_text: str = "") -> None:
        self._scontrol = scontrol_text
        self._sacct = sacct_text
        self._events: list[Event] = []
        self._artifacts: list[Path] = []

    def start(self, ctx: JobContext) -> None:
        parsed = parse_scontrol(self._scontrol) if self._scontrol else {}
        if self._sacct:
            parsed.update({k: v for k, v in parse_sacct(self._sacct).items() if v})
        snap = ctx.output_dir / "events" / "slurm.json"
        snap.parent.mkdir(parents=True, exist_ok=True)
        import json

        snap.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")
        self._artifacts = [snap]
        state = str(parsed.get("JobState") or parsed.get("State") or "")
        code = classify_slurm_state(state)
        if code:
            self._events = [
                Event(reason_code=code, message=state, evidence_path=str(snap), host=ctx.host)
            ]

    def events(self) -> list[Event]:
        return list(self._events)

    def stop(self) -> None:
        return None

    def artifacts(self) -> list[Path]:
        return list(self._artifacts)
