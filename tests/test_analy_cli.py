"""CLI tests for agent analy."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_sidecar.analysis import run_analysis
from agent_sidecar.cli import main
from agent_sidecar.telemetry import write_telemetry


def _seed(run_dir: Path) -> None:
    (run_dir / "events").mkdir(parents=True)
    (run_dir / "assist").mkdir(parents=True)
    (run_dir / "events" / "stderr.tail").write_text(
        "rank 1 called MPI_Abort(comm=MPI_COMM_WORLD, errorcode=2)\n",
        encoding="utf-8",
    )
    write_telemetry(
        run_dir,
        summary={
            "host_count": 0,
            "pid_count": 1,
            "cpu_avg": None,
            "cpu_peak": None,
            "rss_peak_mb": None,
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
        evidence_paths=["events/stderr.tail"],
        reason_code="mpi_abort",
        retry_allowed=False,
        attempt=1,
    )


class TestAnalyCli(unittest.TestCase):
    def test_requires_log_or_run_dir(self) -> None:
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf):
            code = main(["analy"])
        self.assertNotEqual(code, 0)
        self.assertTrue(buf.getvalue())

    def test_analy_writes_analysis_without_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir)

            def boom(*_a, **_k):
                raise AssertionError("opencode must not run with --no-llm")

            buf = io.StringIO()
            with mock.patch("agent_sidecar.opencode_assist.run_opencode_assist", boom):
                with mock.patch("sys.stdout", buf):
                    code = main(["analy", "--run-dir", str(run_dir), "--no-llm"])
            self.assertEqual(code, 0)
            out = buf.getvalue()
            self.assertIn("analy pack=", out)
            self.assertIn("suspected_reason=mpi_abort", out)
            self.assertIn("[agent] summary:", out)
            self.assertIn("MPI", out)
            self.assertTrue((run_dir / "assist" / "analysis.json").is_file())
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(note["suspected_reason"], "mpi_abort")
            self.assertIn(note["summary"].splitlines()[0], out)

    def test_analy_log_alias_without_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir)

            def boom(*_a, **_k):
                raise AssertionError("opencode must not run with --no-llm")

            with mock.patch("agent_sidecar.opencode_assist.run_opencode_assist", boom):
                code = main(["analy", "--log", str(run_dir), "--no-llm"])
            self.assertEqual(code, 0)
            self.assertTrue((run_dir / "assist" / "analysis.json").is_file())

    def test_analy_default_invokes_opencode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir)
            called = {"n": 0}

            def fake_assist(*_a, **_k):
                called["n"] += 1
                return 0

            buf = io.StringIO()
            with mock.patch(
                "agent_sidecar.opencode_assist.run_opencode_assist", fake_assist
            ):
                with mock.patch("sys.stdout", buf):
                    code = main(["analy", "--log", str(run_dir)])
            self.assertEqual(code, 0)
            self.assertEqual(called["n"], 1)
            self.assertIn("llm=1", buf.getvalue())

    def test_analy_conflicting_log_and_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a"
            b = Path(tmp) / "b"
            a.mkdir()
            b.mkdir()
            buf = io.StringIO()
            with mock.patch("sys.stderr", buf):
                code = main(["analy", "--log", str(a), "--run-dir", str(b), "--no-llm"])
            self.assertNotEqual(code, 0)
            self.assertTrue(buf.getvalue())

    def test_analy_llm_uses_injected_runner_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir)
            called = {"n": 0}

            def fake_assist(*_a, **_k):
                called["n"] += 1
                return 0

            with mock.patch(
                "agent_sidecar.opencode_assist.run_opencode_assist", fake_assist
            ):
                run_analysis(
                    run_dir,
                    use_llm=True,
                    opencode_runner=lambda *a, **k: (0, "", ""),
                )
            self.assertEqual(called["n"], 1)


if __name__ == "__main__":
    unittest.main()
