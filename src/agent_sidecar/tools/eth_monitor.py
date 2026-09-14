"""Host ethernet rx/tx adapter (eth-monitor collect contract)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from agent_sidecar.spi import Event, JobContext

CollectLoopFn = Callable[..., None]
LoopImporter = Callable[[], tuple[CollectLoopFn | None, str | None]]


def import_collect_loop() -> tuple[CollectLoopFn | None, str | None]:
    try:
        from eth_monitor.collect import collect_loop
    except ImportError as exc:
        return None, str(exc)
    return collect_loop, None


class EthMonitor:
    name = "eth-monitor"

    def __init__(
        self,
        collect_loop_fn: CollectLoopFn | None = None,
        loop_importer: LoopImporter | None = None,
    ) -> None:
        self._loop = collect_loop_fn
        self._loop_importer = loop_importer
        self._artifacts: list[Path] = []
        self._ctx: JobContext | None = None
        self._thread: threading.Thread | None = None
        self._stop_file: Path | None = None
        self._import_error: str | None = None

    def start(self, ctx: JobContext) -> None:
        self._ctx = ctx
        loop = self._loop
        if loop is None:
            importer = self._loop_importer or import_collect_loop
            loop, err = importer()
            if err:
                self._import_error = err
                self._write_import_error(ctx, err)
                return
        if loop is None:
            return
        series = ctx.output_dir / "series"
        series.mkdir(parents=True, exist_ok=True)
        self._stop_file = ctx.output_dir / f".collect-stop-eth-{ctx.host}"
        if self._stop_file.exists():
            self._stop_file.unlink()
        kwargs = {
            "output_dir": ctx.output_dir,
            "stop_file": self._stop_file,
            "interval": ctx.interval,
            "host": ctx.host,
        }
        self._thread = threading.Thread(target=loop, kwargs=kwargs, daemon=True)
        self._thread.start()

    def _write_import_error(self, ctx: JobContext, message: str) -> None:
        events = ctx.output_dir / "events"
        events.mkdir(parents=True, exist_ok=True)
        (events / "eth_monitor_import.err").write_text(message + "\n", encoding="utf-8")

    def events(self) -> list[Event]:
        return []

    def stop(self) -> None:
        if self._stop_file is not None:
            self._stop_file.write_text("stop\n", encoding="utf-8")
        if self._thread is not None:
            self._thread.join(timeout=15)
            self._thread = None
        if self._ctx is None:
            return
        series = self._ctx.output_dir / "series"
        if series.is_dir():
            for path in sorted(series.glob("*_net.jsonl")):
                if path not in self._artifacts:
                    self._artifacts.append(path)

    def artifacts(self) -> list[Path]:
        return list(self._artifacts)
