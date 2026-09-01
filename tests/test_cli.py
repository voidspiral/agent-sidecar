"""CLI wiring tests."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from agent_sidecar.argv import parse_agent_argv
from agent_sidecar.cli import cmd_srun, main
from agent_sidecar.spi import reset_supervisors
from agent_sidecar.telemetry import write_telemetry


class TestCli(unittest.TestCase):
    def tearDown(self) -> None:
        reset_supervisors()

    def test_unknown_agent_flag(self) -> None:
        self.assertEqual(main(["srun", "--agent-nope=1", "-n", "1"]), 2)

    def test_srun_uses_wrap_and_passthrough(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seen: dict[str, list[str]] = {}

            def run_sidecar(argv: list[str]) -> int:
                seen["sidecar"] = argv
                return 0

            def run_user(argv: list[str]) -> int:
                seen["user"] = argv
                return 0

            parsed = parse_agent_argv(
                [
                    "srun",
                    "--agent-profile=tools-only",
                    "--agent-output-dir",
                    tmp,
                    "-n",
                    "1",
                    "--",
                    "true",
                ]
            )
            code = cmd_srun(parsed, run_sidecar=run_sidecar, run_user=run_user)
            self.assertEqual(code, 0)
            self.assertIn("--overlap", seen["sidecar"])
            self.assertEqual(seen["user"][0], "srun")
            self.assertIn("true", seen["user"])
            self.assertNotIn("--agent-profile=tools-only", seen["user"])

    def test_verbose_prints_launch_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                [
                    "srun",
                    "--agent-verbose",
                    "--agent-output-dir",
                    tmp,
                    "-n",
                    "1",
                    "--",
                    "true",
                ]
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cmd_srun(
                    parsed,
                    run_sidecar=lambda _argv: 0,
                    run_user=lambda _argv: 0,
                )
            self.assertEqual(code, 0)
            text = buf.getvalue()
            self.assertIn("[agent] profile=tools-only", text)
            self.assertIn("run_dir=", text)

    def test_supervisor_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_telemetry(
                run_dir,
                summary={"ok": True},
                anomalies=[],
                evidence_paths=[],
                reason_code="ok",
                retry_allowed=False,
                attempt=1,
            )
            self.assertEqual(main(["report", "--run-dir", str(run_dir)]), 0)
            code = main(
                [
                    "supervisor",
                    "--job-id",
                    "9",
                    "--host",
                    "h1",
                    "--output-dir",
                    str(run_dir),
                    "--skills",
                    "proc-monitor",
                    "--once",
                ]
            )
            self.assertEqual(code, 0)

    def test_sbatch_requires_script(self) -> None:
        self.assertEqual(main(["sbatch"]), 2)
