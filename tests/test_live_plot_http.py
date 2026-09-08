"""Live plot HTTP server tests (no real browser)."""

from __future__ import annotations

import json
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import http.client
import tempfile
import unittest
from pathlib import Path

from agent_sidecar.live_plot_http import LivePlotServer
from agent_sidecar.telemetry import ensure_run_layout


class TestLivePlotHttp(unittest.TestCase):
    def test_page_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            sample = {
                "ts": 1.0,
                "host": "cn1",
                "pid": 7,
                "cpu_pct": 40.0,
                "rss_mb": 8.0,
                "io_read_bps": 0.0,
                "io_write_bps": 2.0,
                "rank": 0,
            }
            (run_dir / "series" / "cn1_pid7.jsonl").write_text(
                json.dumps(sample) + "\n", encoding="utf-8"
            )
            server = LivePlotServer(host="127.0.0.1", port=0)
            url = server.start(run_dir)
            try:
                self.assertTrue(url.startswith("http://127.0.0.1:"))
                host, port_s = url.rsplit("://", 1)[1].split(":")
                conn = http.client.HTTPConnection(host, int(port_s), timeout=2)
                conn.request("GET", "/")
                page = conn.getresponse()
                body = page.read().decode("utf-8")
                self.assertEqual(page.status, 200)
                self.assertIn("<canvas", body)
                self.assertIn("cpu_pct", body)
                self.assertIn("已运行时间 (s)", body)
                self.assertIn("CPU (%)", body)
                self.assertIn("RSS (MB)", body)
                self.assertIn("read (B/s)", body)
                self.assertIn("write (B/s)", body)
                self.assertIn("相对首个采样点", body)
                self.assertNotIn("cdn.jsdelivr", body)
                conn.request("GET", "/api/snapshot")
                snap_resp = conn.getresponse()
                snap = json.loads(snap_resp.read().decode("utf-8"))
                self.assertEqual(snap_resp.status, 200)
                cpu = snap["metrics"]["cpu_pct"]
                self.assertEqual(len(cpu), 1)
                self.assertEqual(cpu[0]["label"], "cn1 r0")
                conn.request("GET", "/chart.umd.min.js")
                js = conn.getresponse()
                self.assertEqual(js.status, 200)
                js.read()
                conn.close()
            finally:
                server.stop()
