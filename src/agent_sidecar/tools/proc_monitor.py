"""Process-level CPU/RSS/IO adapter (mpi-monitor collect contract)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agent_sidecar.spi import Event, JobContext

SAMPLE_KEYS = (
    "ts",
    "host",
    "pid",
    "cpu_pct",
    "rss_mb",
    "io_read_bps",
    "io_write_bps",
)

EXCLUDE_COMM = {
    "srun",
    "mpirun",
    "mpiexec",
    "orted",
    "orterun",
    "prted",
    "prterun",
    "sshd",
    "ssh",
    "hydra_pmi_proxy",
}


def sample_valid(sample: dict[str, Any]) -> bool:
    return all(k in sample for k in SAMPLE_KEYS)


def should_exclude(comm: str, pid: int, collector_pid: int | None) -> bool:
    if collector_pid is not None and pid == collector_pid:
        return True
    return comm in EXCLUDE_COMM


CollectFn = Callable[..., list[dict[str, Any]]]


class ProcMonitor:
    name = "proc-monitor"

    def __init__(self, collect_fn: CollectFn | None = None) -> None:
        self._collect = collect_fn
        self._samples: list[dict[str, Any]] = []
        self._artifacts: list[Path] = []
        self._ctx: JobContext | None = None

    def start(self, ctx: JobContext) -> None:
        self._ctx = ctx
        if self._collect is None:
            self._samples = []
            return
        raw = self._collect(ctx)
        self._samples = [s for s in raw if sample_valid(s)]
        series = ctx.output_dir / "series"
        series.mkdir(parents=True, exist_ok=True)
        for sample in self._samples:
            path = series / f"{sample['host']}_pid{sample['pid']}.jsonl"
            with path.open("a", encoding="utf-8") as fh:
                import json

                fh.write(json.dumps(sample) + "\n")
            if path not in self._artifacts:
                self._artifacts.append(path)

    def events(self) -> list[Event]:
        return []

    def stop(self) -> None:
        return None

    def artifacts(self) -> list[Path]:
        return list(self._artifacts)
