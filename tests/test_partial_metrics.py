"""Partial CPU/RSS/IO samples stay numeric only where the collector had data."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_sidecar.analysis.resource_hints import chinese_summary
from agent_sidecar.live_plot import LivePlotIngest
from agent_sidecar.report import _metrics_line
from agent_sidecar.telemetry import ensure_run_layout, summarize_series
from agent_sidecar.tools.plot import metric_series
from agent_sidecar.tools.proc_monitor import sample_valid


def _sample(**overrides: object) -> dict:
    rec = {
        "ts": 1.0,
        "host": "cn33",
        "pid": 9,
        "cpu_pct": 0.0,
        "rss_mb": 12.0,
        "io_read_bps": None,
        "io_write_bps": None,
        "unavailable": ["io"],
    }
    rec.update(overrides)
    return rec


class TestPartialMetrics(unittest.TestCase):
    def test_sample_valid_accepts_one_nonzero_metric(self) -> None:
        self.assertTrue(sample_valid(_sample()))
        self.assertFalse(
            sample_valid(
                _sample(cpu_pct=0, rss_mb=0, io_read_bps=0, io_write_bps=0, unavailable=None)
            )
        )

    def test_summary_keeps_cpu_and_null_io(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            ensure_run_layout(run)
            path = run / "series" / "cn33_pid9.jsonl"
            path.write_text(json.dumps(_sample(cpu_pct=40.0)) + "\n", encoding="utf-8")
            summary = summarize_series(run)
            self.assertEqual(summary["cpu_peak"], 40.0)
            self.assertIsNone(summary["io_read_bps_sum"])
            self.assertIsNone(summary["io_write_bps_sum"])
            self.assertIn("io", summary["unavailable"])

    def test_zero_io_is_a_number_without_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            ensure_run_layout(run)
            rec = _sample(cpu_pct=10.0, io_read_bps=0, io_write_bps=0)
            rec.pop("unavailable")
            (run / "series" / "cn33_pid9.jsonl").write_text(
                json.dumps(rec) + "\n", encoding="utf-8"
            )
            summary = summarize_series(run)
            self.assertEqual(summary["io_read_bps_sum"], 0.0)
            self.assertEqual(summary["unavailable"], [])

    def test_live_snapshot_skips_null_io_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            ensure_run_layout(run)
            (run / "series" / "cn33_pid9.jsonl").write_text(
                json.dumps(_sample(cpu_pct=15.0)) + "\n", encoding="utf-8"
            )
            snap = LivePlotIngest(run).poll()
            self.assertEqual(snap["metrics"]["cpu_pct"][0]["points"], [[0.0, 15.0]])
            self.assertEqual(snap["metrics"]["io_read_bps"][0]["points"], [])
            self.assertIn("io", snap["unavailable"])
            html = (
                Path(__file__).resolve().parents[1]
                / "src/agent_sidecar/static/live_plot.html"
            ).read_text(encoding="utf-8")
            self.assertIn("CONFIG_TASK_IO_ACCOUNTING", html)
            self.assertIn("无权限读 /proc/<pid>/io", html)

    def test_null_io_does_not_plot_a_flat_zero(self) -> None:
        rows = [_sample(cpu_pct=3.0)]
        _xs, ys = metric_series(rows, "io_read_bps")
        self.assertEqual(ys, [])
        cpu_xs, cpu_ys = metric_series(rows, "cpu_pct")
        self.assertEqual(cpu_ys, [3.0])
        self.assertEqual(cpu_xs, [1.0])

    def test_chinese_note_names_the_kernel_option(self) -> None:
        text = chinese_summary(
            {
                "reason_code": "ok",
                "anomalies": [],
                "summary": {
                    "exit_code": 0,
                    "host_count": 1,
                    "pid_count": 1,
                    "cpu_peak": 40.0,
                    "cpu_avg": 40.0,
                    "rss_peak_mb": 12.0,
                    "io_read_bps_sum": None,
                    "io_write_bps_sum": None,
                    "unavailable": ["io"],
                },
            }
        )
        self.assertIn("CONFIG_TASK_IO_ACCOUNTING", text)
        self.assertIn("cpu_peak=40", text)
        self.assertIn("不是作业没有 I/O", text)

    def test_zero_io_note_does_not_mention_the_kernel_option(self) -> None:
        text = chinese_summary(
            {
                "reason_code": "ok",
                "anomalies": [],
                "summary": {
                    "exit_code": 0,
                    "pid_count": 1,
                    "cpu_peak": 40.0,
                    "io_read_bps_sum": 0,
                    "io_write_bps_sum": 0,
                },
            }
        )
        self.assertNotIn("CONFIG_TASK_IO_ACCOUNTING", text)

    def test_quiet_report_does_not_print_null_io_as_zero(self) -> None:
        line = _metrics_line(
            {
                "cpu_avg": 10.0,
                "cpu_peak": 20.0,
                "rss_peak_mb": 12.0,
                "io_read_bps_sum": None,
                "io_write_bps_sum": None,
            }
        )
        self.assertIsNotNone(line)
        assert line is not None
        self.assertNotIn("io_r/w", line)
        self.assertIn("cpu avg/peak", line)
