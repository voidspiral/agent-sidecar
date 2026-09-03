"""Injectable OpenCode job-assist; no real binary, no network."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sidecar.opencode_assist import (
    DEFAULT_TIMEOUT,
    OpenCodeError,
    build_assist_prompt,
    default_opencode_runner,
    note_summary,
)
from agent_sidecar.telemetry import write_telemetry


def _telemetry(**extra):
    doc = {
        "summary": {"cpu_avg": 1.0, "pid_count": 1, "exit_code": 0},
        "anomalies": [{"reason_code": "cpu_idle"}],
        "reason_code": "cpu_idle",
        "evidence_paths": ["series/h1_pid9.jsonl"],
        "collect_errors": {},
    }
    doc.update(extra)
    return doc


class TestOpenCodeAssist(unittest.TestCase):
    def test_prompt_is_contract_not_jsonl(self) -> None:
        series_line = (
            '{"ts":1,"host":"h1","pid":9,"cpu_pct":1.0,"rss_mb":2.0,'
            '"io_read_bps":3.0,"io_write_bps":4.0}'
        )
        prompt = build_assist_prompt(_telemetry(), Path("/tmp/run"))
        self.assertIn("cpu_idle", prompt)
        self.assertIn("assist/job.json", prompt)
        self.assertIn("reason_code", prompt)
        self.assertNotIn(series_line, prompt)
        self.assertIn("scancel", prompt.lower())

    def test_prompt_requires_chinese_summary(self) -> None:
        prompt = build_assist_prompt(_telemetry(), Path("/tmp/run"))
        self.assertIn("简体中文", prompt)
        self.assertIn("improvement suggestions", prompt)
        self.assertIn("分条", prompt)

    def test_launch_failure_asks_for_corrected_command(self) -> None:
        prompt = build_assist_prompt(
            _telemetry(
                reason_code="execution_error",
                summary={"pid_count": 0, "host_count": 0, "exit_code": 127},
                anomalies=[],
            ),
            Path("/tmp/run"),
        )
        self.assertIn("execution_error", prompt)
        self.assertIn("agent srun", prompt)

    def test_default_runner_missing_binary(self) -> None:
        with patch("agent_sidecar.opencode_assist.shutil.which", return_value=None):
            with self.assertRaises(OpenCodeError) as ctx:
                default_opencode_runner(
                    ["opencode", "run", "--dir", ".", "hi"],
                    cwd=".",
                    timeout=1,
                    env={},
                )
        self.assertEqual(ctx.exception.code, "opencode_missing")

    def test_default_runner_returns_when_note_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "job.json"

            def writer() -> None:
                time.sleep(0.2)
                note.write_text(
                    json.dumps({"summary": "done", "actions": []}),
                    encoding="utf-8",
                )

            threading.Thread(target=writer, daemon=True).start()
            started = time.monotonic()
            rc, stdout, stderr = default_opencode_runner(
                ["sleep", "30"],
                tmp,
                timeout=10,
                env={},
                note_path=note,
            )
            elapsed = time.monotonic() - started
            self.assertEqual(rc, 0)
            self.assertEqual(stdout, "")
            self.assertEqual(stderr, "")
            self.assertLess(elapsed, 5)
            self.assertEqual(note_summary(note), "done")

    def test_default_runner_cancel_kills_process(self) -> None:
        cancel = threading.Event()

        def setter() -> None:
            time.sleep(0.2)
            cancel.set()

        threading.Thread(target=setter, daemon=True).start()
        started = time.monotonic()
        with self.assertRaises(OpenCodeError) as ctx:
            default_opencode_runner(
                ["sleep", "30"],
                ".",
                timeout=10,
                env={},
                cancel=cancel,
            )
        self.assertEqual(ctx.exception.code, "opencode_cancelled")
        self.assertLess(time.monotonic() - started, 5)

    def test_default_runner_timeout_message_is_short(self) -> None:
        with self.assertRaises(OpenCodeError) as ctx:
            default_opencode_runner(
                ["sleep", "30"],
                ".",
                timeout=0.3,
                env={},
            )
        self.assertEqual(ctx.exception.code, "opencode_timeout")
        self.assertIn("0.3", ctx.exception.message)
        self.assertNotIn("sleep", ctx.exception.message)

    def test_model_flag_only_from_opencode_env(self) -> None:
        from agent_sidecar.assist import run_job_assist

        def runner(argv, cwd, timeout, env=None):
            runner.argv = argv
            return 0, "ok", ""

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_telemetry(
                run_dir,
                summary={"exit_code": 0},
                anomalies=[],
                evidence_paths=[],
                reason_code="ok",
                retry_allowed=False,
                attempt=1,
                extra={"collect_errors": {}},
            )
            with patch.dict(os.environ, {"AGENT_LLM_MODEL": "deepseek-v4-flash"}, clear=False):
                os.environ.pop("AGENT_OPENCODE_MODEL", None)
                run_job_assist(run_dir, opencode_runner=runner, user_exit=0)
            self.assertNotIn("--model", runner.argv)
            with patch.dict(os.environ, {"AGENT_OPENCODE_MODEL": "anthropic/deepseek-v4-flash"}):
                run_job_assist(run_dir, opencode_runner=runner, user_exit=0)
            self.assertIn("--model", runner.argv)
            self.assertIn("anthropic/deepseek-v4-flash", runner.argv)

    def test_default_timeout_covers_slow_job_assist(self) -> None:
        self.assertGreaterEqual(DEFAULT_TIMEOUT, 300.0)
