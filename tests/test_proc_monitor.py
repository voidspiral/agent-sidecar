"""proc-monitor adapter tests (mocked mpi-monitor)."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from agent_sidecar.spi import JobContext
from agent_sidecar.tools.proc_monitor import ProcMonitor, sample_valid, should_exclude


def _fake_collect(ctx: JobContext) -> list[dict]:
    return [
        {
            "ts": 1.0,
            "host": ctx.host,
            "pid": 9,
            "cpu_pct": 12.0,
            "rss_mb": 32.0,
            "io_read_bps": 1.0,
            "io_write_bps": 2.0,
        }
    ]


class TestProcMonitor(unittest.TestCase):
    def test_schema_and_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = JobContext(job_id="1", host="h1", output_dir=Path(tmp))
            tool = ProcMonitor(collect_fn=_fake_collect)
            tool.start(ctx)
            self.assertTrue(tool.artifacts())
            sample = _fake_collect(ctx)[0]
            self.assertTrue(sample_valid(sample))
            for key in ("ts", "host", "pid", "cpu_pct", "rss_mb", "io_read_bps", "io_write_bps"):
                self.assertIn(key, sample)

    def test_excludes_launchers(self) -> None:
        self.assertTrue(should_exclude("srun", 1, None))
        self.assertTrue(should_exclude("mpirun", 2, None))
        self.assertTrue(should_exclude("orted", 3, None))
        self.assertTrue(should_exclude("sshd", 4, None))
        self.assertTrue(should_exclude("app", 5, 5))
        self.assertFalse(should_exclude("app", 6, 5))

    def test_collect_loop_runs_until_stop(self) -> None:
        started = threading.Event()
        seen: dict[str, object] = {}

        def fake_loop(*, match, output_dir, stop_file, interval, host, **_k):
            seen["match"] = match
            seen["interval"] = interval
            seen["host"] = host
            seen["output_dir"] = output_dir
            seen["stop_file"] = stop_file
            series = Path(output_dir) / "series"
            series.mkdir(parents=True, exist_ok=True)
            sample = {
                "ts": 1.0,
                "host": host,
                "pid": 99,
                "cpu_pct": 5.0,
                "rss_mb": 8.0,
                "io_read_bps": 1.0,
                "io_write_bps": 2.0,
            }
            (series / f"{host}_pid99.jsonl").write_text(
                json.dumps(sample) + "\n", encoding="utf-8"
            )
            started.set()
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                if Path(stop_file).exists():
                    seen["stopped"] = True
                    return
                time.sleep(0.02)
            seen["stopped"] = False

        with tempfile.TemporaryDirectory() as tmp:
            ctx = JobContext(
                job_id="1",
                host="h1",
                output_dir=Path(tmp),
                match="mpi_io_load",
                interval=0.5,
            )
            tool = ProcMonitor(collect_loop_fn=fake_loop)
            tool.start(ctx)
            self.assertTrue(started.wait(timeout=1.0))
            tool.stop()
            self.assertTrue(seen.get("stopped"))
            self.assertEqual(seen["match"], "mpi_io_load")
            self.assertEqual(seen["interval"], 0.5)
            self.assertEqual(seen["host"], "h1")
            arts = [p.name for p in tool.artifacts()]
            self.assertIn("h1_pid99.jsonl", arts)

    def test_import_failure_writes_collect_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = JobContext(
                job_id="1",
                host="h1",
                output_dir=Path(tmp),
                match="app",
            )
            tool = ProcMonitor(loop_importer=lambda: (None, "no mpi_monitor"))
            tool.start(ctx)
            tool.stop()
            err = Path(tmp) / "events" / "mpi_monitor_import.err"
            self.assertTrue(err.is_file())
            self.assertIn("no mpi_monitor", err.read_text(encoding="utf-8"))
            self.assertFalse(tool.artifacts())
