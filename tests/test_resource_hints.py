"""Deterministic wrap notes from telemetry summary (healthy jobs included)."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import unittest

from agent_sidecar.analysis.resource_hints import chinese_summary


class TestResourceHints(unittest.TestCase):
    def test_healthy_job_always_has_suggestion_item(self) -> None:
        text = chinese_summary(
            {
                "reason_code": "ok",
                "anomalies": [],
                "summary": {
                    "exit_code": 0,
                    "host_count": 2,
                    "pid_count": 2,
                    "cpu_avg": 40.0,
                    "cpu_peak": 55.0,
                    "rss_peak_mb": 128.0,
                    "io_read_bps_sum": 10.0,
                    "io_write_bps_sum": 10.0,
                    "eth_rx_bps_peak": None,
                    "eth_tx_bps_peak": None,
                },
            }
        )
        self.assertIn("1. 结论", text)
        self.assertIn("2. 采集", text)
        self.assertIn("3. 异常：无工具异常", text)
        self.assertIn("4. 建议", text)
        self.assertIn("pid_count=2", text)
        self.assertIn("cpu_peak=55", text)
        self.assertNotIn("{", text)

    def test_exit_zero_no_pids_advises_match(self) -> None:
        text = chinese_summary(
            {
                "reason_code": "ok",
                "anomalies": [],
                "summary": {
                    "exit_code": 0,
                    "host_count": 0,
                    "pid_count": 0,
                    "cpu_peak": None,
                },
            }
        )
        self.assertIn("4. 建议", text)
        self.assertIn("--agent-match", text)

    def test_low_cpu_peak_with_pids(self) -> None:
        text = chinese_summary(
            {
                "reason_code": "ok",
                "anomalies": [],
                "summary": {
                    "exit_code": 0,
                    "pid_count": 1,
                    "cpu_peak": 5.0,
                    "cpu_avg": 2.0,
                },
            }
        )
        self.assertIn("--interval", text)

    def test_high_cpu_peak(self) -> None:
        text = chinese_summary(
            {
                "reason_code": "ok",
                "anomalies": [],
                "summary": {"exit_code": 0, "pid_count": 4, "cpu_peak": 95.0},
            }
        )
        self.assertIn("--cpus-per-task", text)

    def test_ethernet_is_host_nic_not_mpi(self) -> None:
        text = chinese_summary(
            {
                "reason_code": "ok",
                "anomalies": [],
                "summary": {
                    "exit_code": 0,
                    "pid_count": 1,
                    "cpu_peak": 40.0,
                    "eth_rx_bps_peak": 1e8,
                    "eth_tx_bps_peak": 2e8,
                },
            }
        )
        self.assertIn("NIC", text)
        self.assertIn("不是 MPI", text)

    def test_does_not_embed_jsonl_body(self) -> None:
        line = '{"ts":1,"host":"h1","pid":9,"cpu_pct":99.0}'
        text = chinese_summary(
            {
                "reason_code": "ok",
                "anomalies": [],
                "summary": {"exit_code": 0, "pid_count": 1, "cpu_peak": 40.0},
                "evidence_paths": ["series/h1_pid9.jsonl"],
            }
        )
        self.assertNotIn(line, text)
        self.assertNotIn("cpu_pct", text)
