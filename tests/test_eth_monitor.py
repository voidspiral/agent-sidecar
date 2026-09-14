"""eth-monitor adapter tests (mocked collect_loop)."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import tempfile
import unittest
from pathlib import Path

from agent_sidecar.spi import JobContext
from agent_sidecar.tools.eth_monitor import EthMonitor


class TestEthMonitor(unittest.TestCase):
    def test_import_failure_is_collect_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool = EthMonitor(loop_importer=lambda: (None, "no eth_monitor"))
            tool.start(JobContext(job_id="1", host="h1", output_dir=Path(tmp)))
            tool.stop()
            err = Path(tmp) / "events" / "eth_monitor_import.err"
            self.assertTrue(err.is_file())
            self.assertIn("no eth_monitor", err.read_text(encoding="utf-8"))
            self.assertEqual(tool.events(), [])

    def test_loop_runs_until_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seen: dict[str, object] = {}

            def loop(**kwargs):
                seen.update(kwargs)
                Path(kwargs["stop_file"]).write_text("wait\n", encoding="utf-8")

            ctx = JobContext(job_id="1", host="cn1", output_dir=Path(tmp), interval=0.5)
            tool = EthMonitor(collect_loop_fn=loop)
            tool.start(ctx)
            tool.stop()
            self.assertEqual(seen["host"], "cn1")
            self.assertEqual(seen["interval"], 0.5)
            self.assertEqual(seen["output_dir"], ctx.output_dir)
            self.assertTrue(Path(seen["stop_file"]).is_file())
            self.assertNotIn("match", seen)

    def test_stop_lists_net_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = JobContext(job_id="1", host="h1", output_dir=Path(tmp))
            series = Path(tmp) / "series"
            series.mkdir()
            net = series / "h1_net.jsonl"
            net.write_text(
                json.dumps(
                    {
                        "ts": 1.0,
                        "host": "h1",
                        "iface": "eth0",
                        "eth_rx_bps": 1.0,
                        "eth_tx_bps": 2.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            tool = EthMonitor(collect_loop_fn=lambda **_k: None)
            tool.start(ctx)
            tool.stop()
            self.assertIn(net, tool.artifacts())


if __name__ == "__main__":
    unittest.main()
