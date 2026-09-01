"""One sidecar per (job_id, host); multiple skills share it."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from pathlib import Path
import unittest

from agent_sidecar.spi import (
    JobContext,
    SupervisorConflict,
    reset_supervisors,
    start_supervisor,
)


class NamedTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.started = False

    def start(self, ctx: JobContext) -> None:
        self.started = True

    def events(self) -> list:
        return []

    def stop(self) -> None:
        return None

    def artifacts(self) -> list:
        return []


class TestSupervisorOnce(unittest.TestCase):
    def setUp(self) -> None:
        reset_supervisors()

    def tearDown(self) -> None:
        reset_supervisors()

    def test_second_start_same_job_host_conflicts(self) -> None:
        ctx = JobContext(job_id="42", host="n1", output_dir=Path("/tmp/x"))
        start_supervisor("42", "n1", [NamedTool("a")], ctx)
        with self.assertRaises(SupervisorConflict):
            start_supervisor("42", "n1", [NamedTool("b")], ctx)

    def test_two_skills_share_one_sidecar(self) -> None:
        a = NamedTool("proc-monitor")
        b = NamedTool("node-diag")
        ctx = JobContext(job_id="42", host="n1", output_dir=Path("/tmp/x"))
        sup = start_supervisor("42", "n1", [a, b], ctx)
        self.assertTrue(a.started and b.started)
        self.assertEqual(len(sup.plugins), 2)
        self.assertIs(sup.plugins[0], a)
        self.assertIs(sup.plugins[1], b)
