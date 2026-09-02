"""Injectable OpenCode job-assist; no real binary, no network."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sidecar.opencode_assist import (
    OpenCodeError,
    build_assist_prompt,
    default_opencode_runner,
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
