"""proc-monitor adapter tests (mocked mpi-monitor)."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
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
