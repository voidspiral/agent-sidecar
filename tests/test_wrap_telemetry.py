"""Wrap-end JobTelemetry aggregates series and tool artifacts."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import tempfile
import unittest
from pathlib import Path

from agent_sidecar.argv import parse_agent_argv
from agent_sidecar.run import wrap_srun
from agent_sidecar.telemetry import load_telemetry


def _wrap(tmp: str, *, populate):
    parsed = parse_agent_argv(
        ["srun", "--agent-output-dir", tmp, "-n", "1", "--", "true"]
    )

    def run_sidecar(argv: list[str]) -> int:
        out = Path(argv[argv.index("--output-dir") + 1])
        populate(out)
        return 0

    code, run_dir, _plan = wrap_srun(
        parsed,
        env={},
        run_sidecar=run_sidecar,
        run_user=lambda _argv: 0,
    )
    return code, run_dir


class TestWrapTelemetry(unittest.TestCase):
    def test_summary_from_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:

            def populate(out: Path) -> None:
                series = out / "series"
                series.mkdir(parents=True, exist_ok=True)
                (series / "h1_pid10.jsonl").write_text(
                    json.dumps(
                        {
                            "ts": 1,
                            "host": "h1",
                            "pid": 10,
                            "cpu_pct": 10.0,
                            "rss_mb": 100.0,
                            "io_read_bps": 8.0,
                            "io_write_bps": 4.0,
                        }
                    )
                    + "\n"
                    + json.dumps(
                        {
                            "ts": 2,
                            "host": "h1",
                            "pid": 10,
                            "cpu_pct": 30.0,
                            "rss_mb": 200.0,
                            "io_read_bps": 2.0,
                            "io_write_bps": 6.0,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

            code, run_dir = _wrap(tmp, populate=populate)
            self.assertEqual(code, 0)
            doc = load_telemetry(run_dir)
            summary = doc["summary"]
            for key in (
                "cpu_avg",
                "cpu_peak",
                "rss_peak_mb",
                "io_read_bps_sum",
                "io_write_bps_sum",
                "host_count",
                "pid_count",
            ):
                self.assertIn(key, summary)
            self.assertEqual(summary["cpu_avg"], 20.0)
            self.assertEqual(summary["cpu_peak"], 30.0)
            self.assertEqual(summary["rss_peak_mb"], 200.0)
            self.assertEqual(summary["io_read_bps_sum"], 10.0)
            self.assertEqual(summary["io_write_bps_sum"], 10.0)
            self.assertEqual(summary["host_count"], 1)
            self.assertEqual(summary["pid_count"], 1)

    def test_empty_series_uses_nulls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, run_dir = _wrap(tmp, populate=lambda _out: None)
            self.assertEqual(code, 0)
            summary = load_telemetry(run_dir)["summary"]
            self.assertIsNone(summary["cpu_avg"])
            self.assertIsNone(summary["cpu_peak"])
            self.assertIsNone(summary["rss_peak_mb"])
            self.assertEqual(summary["host_count"], 0)
            self.assertEqual(summary["pid_count"], 0)

    def test_events_become_anomalies_and_reason_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:

            def populate(out: Path) -> None:
                events = out / "events"
                events.mkdir(parents=True, exist_ok=True)
                (events / "stderr.tail").write_text(
                    "rank 0: MPI_Abort(comm=MPI_COMM_WORLD, errorcode=1)\n",
                    encoding="utf-8",
                )
                (events / "slurm.json").write_text(
                    json.dumps({"JobState": "OUT_OF_MEMORY"}) + "\n",
                    encoding="utf-8",
                )

            code, run_dir = _wrap(tmp, populate=populate)
            self.assertEqual(code, 0)
            doc = load_telemetry(run_dir)
            codes = [a["reason_code"] for a in doc["anomalies"]]
            self.assertIn("mpi_abort", codes)
            self.assertIn("slurm_oom", codes)
            self.assertIn(doc["reason_code"], codes)
            self.assertNotEqual(doc["reason_code"], "ok")
