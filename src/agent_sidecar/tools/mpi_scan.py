"""Scan captured MPI/launcher stderr for abort patterns."""

from __future__ import annotations

from pathlib import Path

from agent_sidecar.chart_markers import record_event_marker
from agent_sidecar.classify import classify_mpi_text
from agent_sidecar.spi import Event, JobContext


class MpiScan:
    name = "mpi-scan"

    def __init__(self, stderr_text: str | None = None, stderr_path: Path | None = None) -> None:
        self._text = stderr_text
        self._path = stderr_path
        self._events: list[Event] = []
        self._artifacts: list[Path] = []

    def start(self, ctx: JobContext) -> None:
        text = self._text
        if text is None and self._path is not None and self._path.is_file():
            text = self._path.read_text(encoding="utf-8", errors="replace")
        if text is None:
            return
        capture = ctx.output_dir / "events" / "stderr.tail"
        capture.parent.mkdir(parents=True, exist_ok=True)
        capture.write_text(text[-8000:], encoding="utf-8")
        self._artifacts = [capture]
        code = classify_mpi_text(text)
        if code:
            ev = Event(
                reason_code=code,
                message="mpi runtime fault",
                evidence_path=str(capture),
                host=ctx.host,
            )
            self._events = [record_event_marker(ctx.output_dir, ev)]

    def events(self) -> list[Event]:
        return list(self._events)

    def stop(self) -> None:
        return None

    def artifacts(self) -> list[Path]:
        return list(self._artifacts)


def scan_stderr(text: str) -> str | None:
    return classify_mpi_text(text)
