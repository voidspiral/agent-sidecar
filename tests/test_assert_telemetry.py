"""assert_telemetry.py checks telemetry.json reason_code / pid_count / pack."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assert_telemetry.py"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


class TestAssertTelemetry(unittest.TestCase):
    def test_ok_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "telemetry.json").write_text(
                json.dumps(
                    {
                        "reason_code": "mpi_deadlock",
                        "summary": {"pid_count": 2, "exit_code": 1},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            proc = _run(["--run-dir", str(run_dir), "--reason", "mpi_deadlock", "--pid-min", "1"])
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_wrong_reason_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "telemetry.json").write_text(
                json.dumps({"reason_code": "timeout", "summary": {"pid_count": 1}}) + "\n",
                encoding="utf-8",
            )
            proc = _run(["--run-dir", str(run_dir), "--reason", "mpi_deadlock"])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("reason_code", proc.stderr)

    def test_pack_from_analysis_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "assist").mkdir()
            (run_dir / "telemetry.json").write_text(
                json.dumps({"reason_code": "mpi_fpe", "summary": {"pid_count": 2}}) + "\n",
                encoding="utf-8",
            )
            (run_dir / "assist" / "analysis.json").write_text(
                json.dumps({"pack": "stub", "reason_code": "mpi_fpe"}) + "\n",
                encoding="utf-8",
            )
            proc = _run(
                ["--run-dir", str(run_dir), "--reason", "mpi_fpe", "--pack", "stub"]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_missing_telemetry_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run(["--run-dir", tmp, "--reason", "ok"])
            self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
