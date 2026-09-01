"""Per-node sidecar: load tool plugins, one instance per (job_id, host)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class SupervisorConflict(Exception):
    """A sidecar is already running for this job id and host."""


@dataclass
class JobContext:
    job_id: str
    host: str
    output_dir: Path
    match: str | None = None
    interval: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    reason_code: str
    message: str = ""
    evidence_path: str | None = None
    host: str | None = None


class ToolPlugin(Protocol):
    name: str

    def start(self, ctx: JobContext) -> None: ...

    def events(self) -> list[Event]: ...

    def stop(self) -> None: ...

    def artifacts(self) -> list[Path]: ...


_ACTIVE: dict[tuple[str, str], "Supervisor"] = {}


def active_supervisors() -> dict[tuple[str, str], Supervisor]:
    return dict(_ACTIVE)


def reset_supervisors() -> None:
    _ACTIVE.clear()


class Supervisor:
    def __init__(self, job_id: str, host: str, plugins: list[ToolPlugin]) -> None:
        self.job_id = job_id
        self.host = host
        self.plugins = list(plugins)
        self.running = False
        self._ctx: JobContext | None = None

    def start(self, ctx: JobContext) -> None:
        key = (self.job_id, self.host)
        existing = _ACTIVE.get(key)
        if existing is not None and existing.running and existing is not self:
            raise SupervisorConflict(f"sidecar already running for {key}")
        _ACTIVE[key] = self
        self._ctx = ctx
        self.running = True
        for plugin in self.plugins:
            plugin.start(ctx)

    def events(self) -> list[Event]:
        out: list[Event] = []
        for plugin in self.plugins:
            out.extend(plugin.events())
        return out

    def stop(self) -> None:
        if not self.running:
            return
        for plugin in self.plugins:
            plugin.stop()
        self.running = False

    def artifacts(self) -> list[Path]:
        paths: list[Path] = []
        for plugin in self.plugins:
            paths.extend(plugin.artifacts())
        return paths


def start_supervisor(job_id: str, host: str, plugins: list[ToolPlugin], ctx: JobContext) -> Supervisor:
    key = (job_id, host)
    existing = _ACTIVE.get(key)
    if existing is not None and existing.running:
        raise SupervisorConflict(f"sidecar already running for {key}")
    sup = Supervisor(job_id, host, plugins)
    sup.start(ctx)
    return sup
