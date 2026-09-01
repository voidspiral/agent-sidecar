"""SPI tests with a fake tool plugin."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from pathlib import Path
import unittest

from agent_sidecar.spi import Event, JobContext, Supervisor, reset_supervisors


class FakeTool:
    name = "fake"

    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.sample_count = 0
        self._artifacts: list[Path] = []
        self._emit_anomaly = False

    def start(self, ctx: JobContext) -> None:
        self.started += 1
        self._artifacts = [ctx.output_dir / f"{self.name}.txt"]
        self._artifacts[0].parent.mkdir(parents=True, exist_ok=True)
        self._artifacts[0].write_text("ok\n", encoding="utf-8")
        self.sample_count = 200

    def events(self) -> list[Event]:
        if not self._emit_anomaly:
            return []
        return [Event(reason_code="node_local", message="anomaly")]

    def stop(self) -> None:
        self.stopped += 1

    def artifacts(self) -> list[Path]:
        return list(self._artifacts)


class TestSpi(unittest.TestCase):
    def setUp(self) -> None:
        reset_supervisors()

    def tearDown(self) -> None:
        reset_supervisors()

    def test_start_stop_artifacts_idempotent_stop(self) -> None:
        tool = FakeTool()
        ctx = JobContext(job_id="1", host="h1", output_dir=Path("/tmp/agent-spi-test"))
        sup = Supervisor("1", "h1", [tool])
        sup.start(ctx)
        paths = sup.artifacts()
        self.assertTrue(paths)
        self.assertTrue(paths[0].exists())
        sup.stop()
        sup.stop()
        self.assertEqual(tool.started, 1)
        self.assertEqual(tool.stopped, 1)

    def test_events_are_anomaly_oriented(self) -> None:
        tool = FakeTool()
        ctx = JobContext(job_id="1", host="h1", output_dir=Path("/tmp/agent-spi-test"))
        sup = Supervisor("1", "h1", [tool])
        sup.start(ctx)
        self.assertGreater(tool.sample_count, 1)
        self.assertEqual(sup.events(), [])
        tool._emit_anomaly = True
        self.assertEqual(sup.events()[0].reason_code, "node_local")
        sup.stop()
