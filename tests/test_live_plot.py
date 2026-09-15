"""JSONL tail overlay for live mpi-monitor charts."""

from __future__ import annotations

import json
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from agent_sidecar.live_plot import METRICS, VISIBLE_CAP, LivePlotIngest
from agent_sidecar.telemetry import ensure_run_layout


def _line(ts: float, host: str, pid: int, cpu: float, *, rank=None) -> str:
    rec = {
        "ts": ts,
        "host": host,
        "pid": pid,
        "cpu_pct": cpu,
        "rss_mb": 8.0,
        "io_read_bps": 0.0,
        "io_write_bps": 1.0,
    }
    if rank is not None:
        rec["rank"] = rank
    return json.dumps(rec) + "\n"


class TestLivePlotIngest(unittest.TestCase):
    def test_two_hosts_overlay_cpu_with_rank_legend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            (run_dir / "series" / "cn1_pid1.jsonl").write_text(
                _line(10.0, "cn1", 1, 10.0, rank=0)
                + _line(11.0, "cn1", 1, 20.0, rank=0),
                encoding="utf-8",
            )
            (run_dir / "series" / "cn2_pid2.jsonl").write_text(
                _line(10.0, "cn2", 2, 5.0, rank=1),
                encoding="utf-8",
            )
            snap = LivePlotIngest(run_dir).poll()
            cpu = snap["metrics"]["cpu_pct"]
            self.assertEqual(len(cpu), 2)
            labels = [s["label"] for s in cpu]
            self.assertIn("cn1 r0", labels)
            self.assertIn("cn2 r1", labels)
            by_label = {s["label"]: s for s in cpu}
            self.assertEqual(by_label["cn1 r0"]["points"], [[0.0, 10.0], [1.0, 20.0]])
            self.assertEqual(by_label["cn1 r0"]["host"], "cn1")
            self.assertEqual(by_label["cn1 r0"]["pid"], 1)
            self.assertEqual(by_label["cn1 r0"]["rank"], 0)
            for metric in METRICS:
                self.assertIn(metric, snap["metrics"])

    def test_append_increases_point_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            path = run_dir / "series" / "cn1_pid9.jsonl"
            path.write_text(_line(1.0, "cn1", 9, 1.0), encoding="utf-8")
            ingest = LivePlotIngest(run_dir)
            first = ingest.poll()
            self.assertEqual(len(first["metrics"]["cpu_pct"][0]["points"]), 1)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(_line(2.0, "cn1", 9, 2.0))
            second = ingest.poll()
            pts = second["metrics"]["cpu_pct"][0]["points"]
            self.assertEqual(len(pts), 2)
            self.assertEqual(pts[-1], [1.0, 2.0])
            self.assertEqual(second["metrics"]["cpu_pct"][0]["label"], "cn1 pid 9")

    def test_net_jsonl_overlays_without_pid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            (run_dir / "series" / "cn1_net.jsonl").write_text(
                json.dumps(
                    {
                        "ts": 10.0,
                        "host": "cn1",
                        "iface": "eth0",
                        "eth_rx_bps": 100.0,
                        "eth_tx_bps": 20.0,
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "ts": 11.0,
                        "host": "cn1",
                        "iface": "eth0",
                        "eth_rx_bps": 200.0,
                        "eth_tx_bps": 40.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "series" / "cn2_net.jsonl").write_text(
                json.dumps(
                    {
                        "ts": 10.0,
                        "host": "cn2",
                        "iface": "bond0",
                        "eth_rx_bps": 5.0,
                        "eth_tx_bps": 6.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            snap = LivePlotIngest(run_dir).poll()
            rx = snap["metrics"]["eth_rx_bps"]
            labels = [s["label"] for s in rx]
            self.assertIn("cn1 eth0", labels)
            self.assertIn("cn2 bond0", labels)
            by_label = {s["label"]: s for s in rx}
            self.assertEqual(by_label["cn1 eth0"]["points"], [[0.0, 100.0], [1.0, 200.0]])
            self.assertEqual(snap["metrics"]["cpu_pct"], [])

    def test_net_file_does_not_pollute_process_charts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            (run_dir / "series" / "cn1_pid1.jsonl").write_text(
                _line(10.0, "cn1", 1, 10.0, rank=0),
                encoding="utf-8",
            )
            (run_dir / "series" / "cn1_net.jsonl").write_text(
                json.dumps(
                    {
                        "ts": 10.0,
                        "host": "cn1",
                        "iface": "eth0",
                        "eth_rx_bps": 9.0,
                        "eth_tx_bps": 8.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            snap = LivePlotIngest(run_dir).poll()
            self.assertEqual(len(snap["metrics"]["cpu_pct"]), 1)
            self.assertEqual(snap["metrics"]["cpu_pct"][0]["label"], "cn1 r0")
            self.assertEqual(len(snap["metrics"]["eth_rx_bps"]), 1)

    def test_empty_series_is_empty_not_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            snap = LivePlotIngest(run_dir).poll()
            for metric in METRICS:
                self.assertEqual(snap["metrics"][metric], [])
            self.assertEqual(snap["markers"], [])

    def test_visible_cap_keeps_all_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            for i in range(VISIBLE_CAP + 2):
                (run_dir / "series" / f"h_pid{i}.jsonl").write_text(
                    _line(1.0, "h", i, float(i)),
                    encoding="utf-8",
                )
            snap = LivePlotIngest(run_dir).poll()
            cpu = snap["metrics"]["cpu_pct"]
            self.assertEqual(len(cpu), VISIBLE_CAP + 2)
            visible = [s for s in cpu if s["visible"]]
            hidden = [s for s in cpu if not s["visible"]]
            self.assertEqual(len(visible), VISIBLE_CAP)
            self.assertEqual(len(hidden), 2)
            self.assertGreaterEqual(
                min(s["cpu_peak"] for s in visible),
                max(s["cpu_peak"] for s in hidden),
            )

    def test_markers_use_elapsed_seconds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            (run_dir / "series" / "cn1_pid1.jsonl").write_text(
                _line(10.0, "cn1", 1, 10.0, rank=0)
                + _line(12.0, "cn1", 1, 20.0, rank=0),
                encoding="utf-8",
            )
            (run_dir / "events" / "submit_markers.jsonl").write_text(
                json.dumps(
                    {
                        "ts": 11.0,
                        "reason_code": "mpi_abort",
                        "message": "abort",
                        "evidence_path": "events/stderr.tail",
                        "host": "submit",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            snap = LivePlotIngest(run_dir).poll()
            self.assertEqual(len(snap["markers"]), 1)
            marker = snap["markers"][0]
            self.assertEqual(marker["reason_code"], "mpi_abort")
            self.assertEqual(marker["host"], "submit")
            self.assertEqual(marker["x"], 1.0)
            self.assertEqual(marker["ts"], 11.0)

    def test_markers_append_on_later_poll(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            (run_dir / "series" / "cn1_pid1.jsonl").write_text(
                _line(5.0, "cn1", 1, 1.0),
                encoding="utf-8",
            )
            path = run_dir / "events" / "cn1_markers.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "ts": 5.5,
                        "reason_code": "node_local",
                        "message": "oom",
                        "evidence_path": "events/node-diag.txt",
                        "host": "cn1",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            ingest = LivePlotIngest(run_dir)
            first = ingest.poll()
            self.assertEqual(len(first["markers"]), 1)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": 6.0,
                            "reason_code": "slurm_oom",
                            "message": "oom",
                            "evidence_path": "events/slurm.json",
                            "host": "cn1",
                        }
                    )
                    + "\n"
                )
            second = ingest.poll()
            codes = [m["reason_code"] for m in second["markers"]]
            self.assertEqual(codes, ["node_local", "slurm_oom"])

    def test_markers_without_series_do_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            (run_dir / "events" / "submit_markers.jsonl").write_text(
                json.dumps(
                    {
                        "ts": 99.0,
                        "reason_code": "mpi_segfault",
                        "message": "segv",
                        "evidence_path": "events/stderr.tail",
                        "host": "submit",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            snap = LivePlotIngest(run_dir).poll()
            self.assertEqual(len(snap["markers"]), 1)
            self.assertEqual(snap["markers"][0]["reason_code"], "mpi_segfault")
            self.assertEqual(snap["markers"][0]["ts"], 99.0)
