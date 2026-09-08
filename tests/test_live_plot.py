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

    def test_empty_series_is_empty_not_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            snap = LivePlotIngest(run_dir).poll()
            for metric in METRICS:
                self.assertEqual(snap["metrics"][metric], [])

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
