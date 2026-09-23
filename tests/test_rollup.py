"""rollup_reason_code prefers MPI-specific codes over timeout/slurm_failed."""

from __future__ import annotations

import json
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from agent_sidecar.telemetry import anomalies_from_artifacts, rollup_reason_code


class TestRollupReasonCode(unittest.TestCase):
    def test_empty_uses_exit(self) -> None:
        self.assertEqual(rollup_reason_code([], user_exit=0), "ok")
        self.assertEqual(rollup_reason_code([], user_exit=1), "execution_error")

    def test_deadlock_beats_timeout_file_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            events = run_dir / "events"
            events.mkdir()
            (events / "slurm.json").write_text(
                json.dumps({"JobState": "TIMEOUT"}) + "\n", encoding="utf-8"
            )
            (events / "stderr.tail").write_text(
                "rank 0 deadlock (skip barrier)\n", encoding="utf-8"
            )
            anomalies = anomalies_from_artifacts(run_dir)
            codes = [a["reason_code"] for a in anomalies]
            self.assertIn("timeout", codes)
            self.assertIn("mpi_deadlock", codes)
            self.assertEqual(codes[0], "timeout")
            self.assertEqual(rollup_reason_code(anomalies, user_exit=1), "mpi_deadlock")

    def test_fpe_beats_slurm_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            events = run_dir / "events"
            events.mkdir()
            (events / "slurm.json").write_text(
                json.dumps({"JobState": "FAILED"}) + "\n", encoding="utf-8"
            )
            (events / "stderr.tail").write_text(
                "rank 0 fpe (SIGFPE)\nFloating point exception\n", encoding="utf-8"
            )
            anomalies = anomalies_from_artifacts(run_dir)
            self.assertEqual(rollup_reason_code(anomalies, user_exit=136), "mpi_fpe")

    def test_mpi_abort_still_wins_alone(self) -> None:
        anomalies = [{"reason_code": "mpi_abort"}]
        self.assertEqual(rollup_reason_code(anomalies, user_exit=1), "mpi_abort")


if __name__ == "__main__":
    unittest.main()
