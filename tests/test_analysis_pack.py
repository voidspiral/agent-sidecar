"""Deterministic analysis packs for agent analy / wrap (TDD)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_sidecar.analysis import run_analysis
from agent_sidecar.telemetry import write_telemetry


def _seed_mpi_abort(run_dir: Path, *, with_series: bool = True) -> None:
    (run_dir / "events").mkdir(parents=True, exist_ok=True)
    (run_dir / "series").mkdir(parents=True, exist_ok=True)
    (run_dir / "assist").mkdir(parents=True, exist_ok=True)
    (run_dir / "events" / "stderr.tail").write_text(
        "mpi_fault_abort rank0 working elapsed=2\n"
        "rank 0 called MPI_Abort(comm=MPI_COMM_WORLD, errorcode=1)\n",
        encoding="utf-8",
    )
    if with_series:
        (run_dir / "series" / "cn1_pid100.jsonl").write_text(
            json.dumps(
                {
                    "ts": 1000.0,
                    "host": "cn1",
                    "pid": 100,
                    "cpu_pct": 80.0,
                    "rss_mb": 100.0,
                    "io_read_bps": 0,
                    "io_write_bps": 0,
                    "rank": 0,
                }
            )
            + "\n",
            encoding="utf-8",
        )
    write_telemetry(
        run_dir,
        summary={
            "host_count": 1 if with_series else 0,
            "pid_count": 1 if with_series else 0,
            "cpu_avg": 80.0 if with_series else None,
            "cpu_peak": 80.0 if with_series else None,
            "rss_peak_mb": 100.0 if with_series else None,
            "io_read_bps_sum": 0,
            "io_write_bps_sum": 0,
            "exit_code": 1,
        },
        anomalies=[
            {
                "reason_code": "mpi_abort",
                "message": "mpi runtime fault",
                "evidence_path": "events/stderr.tail",
            }
        ],
        evidence_paths=["meta.json", "telemetry.json", "events/stderr.tail"],
        reason_code="mpi_abort",
        retry_allowed=False,
        attempt=1,
    )


class TestMpiAbortPack(unittest.TestCase):
    def test_writes_analysis_and_job_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed_mpi_abort(run_dir)
            result = run_analysis(run_dir, use_llm=False)
            self.assertEqual(result["pack"], "mpi_abort")
            analysis = json.loads(
                (run_dir / "assist" / "analysis.json").read_text(encoding="utf-8")
            )
            self.assertEqual(analysis["pack"], "mpi_abort")
            self.assertEqual(analysis["reason_code"], "mpi_abort")
            self.assertEqual(analysis.get("abort_rank"), 0)
            self.assertEqual(analysis.get("errorcode"), 1)
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(note["suspected_reason"], "mpi_abort")
            self.assertEqual(note["actions"], [])
            self.assertIn("1.", note["summary"])
            self.assertIn("MPI_Abort", note["summary"])
            tel = json.loads((run_dir / "telemetry.json").read_text(encoding="utf-8"))
            self.assertEqual(tel["reason_code"], "mpi_abort")
            self.assertIn("assist/analysis.json", tel.get("evidence_paths", []))

    def test_preserves_existing_job_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed_mpi_abort(run_dir)
            (run_dir / "assist" / "job.json").write_text(
                json.dumps(
                    {
                        "host": "submit",
                        "summary": "1. 已有 live 笔记",
                        "suspected_reason": "mpi_abort",
                        "evidence_paths": [],
                        "confidence": None,
                        "actions": [],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            run_analysis(run_dir, use_llm=False)
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(note["summary"], "1. 已有 live 笔记")
            self.assertTrue((run_dir / "assist" / "analysis.json").is_file())

    def test_code_scan_requires_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "app.c").write_text("MPI_Abort(MPI_COMM_WORLD, 1);\n", encoding="utf-8")
            _seed_mpi_abort(run_dir)
            run_analysis(run_dir, use_llm=False)
            analysis = json.loads(
                (run_dir / "assist" / "analysis.json").read_text(encoding="utf-8")
            )
            self.assertFalse(analysis.get("code_hits"))

            run_analysis(run_dir, code_root=src, use_llm=False)
            analysis2 = json.loads(
                (run_dir / "assist" / "analysis.json").read_text(encoding="utf-8")
            )
            self.assertTrue(analysis2.get("code_hits"))
            self.assertTrue(
                any("MPI_Abort" in str(h.get("line", "")) for h in analysis2["code_hits"])
            )

    def test_launch_fail_skeleton(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "events").mkdir(parents=True)
            (run_dir / "assist").mkdir(parents=True)
            write_telemetry(
                run_dir,
                summary={
                    "host_count": 0,
                    "pid_count": 0,
                    "cpu_avg": None,
                    "cpu_peak": None,
                    "rss_peak_mb": None,
                    "io_read_bps_sum": 0,
                    "io_write_bps_sum": 0,
                    "exit_code": 127,
                },
                anomalies=[],
                evidence_paths=["telemetry.json"],
                reason_code="execution_error",
                retry_allowed=False,
                attempt=1,
            )
            result = run_analysis(run_dir, use_llm=False)
            self.assertEqual(result["pack"], "launch_fail")
            analysis = json.loads(
                (run_dir / "assist" / "analysis.json").read_text(encoding="utf-8")
            )
            self.assertEqual(analysis["pack"], "launch_fail")
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(note["suspected_reason"], "execution_error")
            self.assertIn("未启动", note["summary"])


if __name__ == "__main__":
    unittest.main()
