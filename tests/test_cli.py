"""CLI wiring tests."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import contextlib
import io
import tempfile
import threading
import time
import unittest
from pathlib import Path

from agent_sidecar.argv import parse_agent_argv
from agent_sidecar.cli import cmd_srun, main
from agent_sidecar.spi import reset_supervisors
from agent_sidecar.telemetry import write_telemetry

sys.path.insert(0, str(_Path(__file__).resolve().parent))
from agent_fakes import NoWatch, noop_opencode


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

    def test_default_srun_is_quiet_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
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
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cmd_srun(
                    parsed,
                    run_sidecar=lambda _a: 0,
                    run_user=lambda _a: 0,
                    opencode_runner=noop_opencode,
                    live_watcher=NoWatch(),
                    tty=False,
                )
            self.assertEqual(code, 0)
            text = buf.getvalue()
            self.assertIn("[agent] sidecar started", text)
            self.assertIn("======== agent report ========", text)
            self.assertNotIn("passthrough=", text)
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
                    opencode_runner=noop_opencode,
                    live_watcher=NoWatch(),
                    tty=False,
                )
            self.assertEqual(code, 0)
            text = buf.getvalue()
            self.assertIn("[agent] profile=job-assist", text)
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

    def test_supervisor_exits_on_agent_stop_file(self) -> None:
        from agent_sidecar.cli import cmd_supervisor

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            started = threading.Event()
            errors: list[BaseException] = []

            def run() -> None:
                started.set()
                try:
                    cmd_supervisor(
                        [
                            "--job-id",
                            "9",
                            "--host",
                            "h1",
                            "--output-dir",
                            str(run_dir),
                            "--skills",
                            "proc-monitor",
                        ]
                    )
                except BaseException as exc:  # pragma: no cover - test helper
                    errors.append(exc)

            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            self.assertTrue(started.wait(2))
            time.sleep(0.3)
            self.assertEqual(errors, [])
            self.assertTrue(thread.is_alive())
            (run_dir / ".agent-stop").write_text("stop\n", encoding="utf-8")
            thread.join(timeout=5)
            self.assertEqual(errors, [])
            self.assertFalse(thread.is_alive())

    def test_sbatch_requires_script(self) -> None:
        self.assertEqual(main(["sbatch"]), 2)
