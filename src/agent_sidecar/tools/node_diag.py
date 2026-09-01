"""Local node diagnostics (OOM / cgroup). Independent of other control planes."""

from __future__ import annotations

import re
from pathlib import Path

from agent_sidecar.spi import Event, JobContext

OOM_RE = re.compile(r"Killed process (\d+)|Out of memory", re.IGNORECASE)


def parse_oom_trace(text: str) -> list[int]:
    pids: list[int] = []
    for m in re.finditer(r"Killed process (\d+)", text):
        pids.append(int(m.group(1)))
    return pids


def parse_cgroup_procs(text: str) -> list[int]:
    pids: list[int] = []
    for line in text.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


class NodeDiag:
    name = "node-diag"

    def __init__(self, dmesg_text: str = "", cgroup_procs: str = "") -> None:
        self._dmesg = dmesg_text
        self._cgroup = cgroup_procs
        self._events: list[Event] = []
        self._artifacts: list[Path] = []

    def start(self, ctx: JobContext) -> None:
        snap = ctx.output_dir / "events" / "node-diag.txt"
        snap.parent.mkdir(parents=True, exist_ok=True)
        oom_pids = parse_oom_trace(self._dmesg)
        cgpids = parse_cgroup_procs(self._cgroup)
        snap.write_text(
            f"oom_pids={oom_pids}\ncgroup_pids={cgpids}\n",
            encoding="utf-8",
        )
        self._artifacts = [snap]
        if oom_pids or OOM_RE.search(self._dmesg):
            self._events = [
                Event(
                    reason_code="node_local",
                    message=f"oom pids={oom_pids}",
                    evidence_path=str(snap),
                    host=ctx.host,
                )
            ]

    def events(self) -> list[Event]:
        return list(self._events)

    def stop(self) -> None:
        return None

    def artifacts(self) -> list[Path]:
        return list(self._artifacts)
