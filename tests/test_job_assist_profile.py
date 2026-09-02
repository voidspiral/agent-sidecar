"""job-assist profile: one submit-host OpenCode spawn after telemetry."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from agent_sidecar.argv import parse_agent_argv
from agent_sidecar.cli import main
from agent_sidecar.run import wrap_srun
from agent_sidecar.telemetry import load_telemetry


SECRET_ENV = {
    "ANTHROPIC_API_KEY": "secret-test",
    "AGENT_LLM_API_KEY": "secret-test",
    "AGENT_LLM_BASE_URL": "https://api.example.com/v1",
    "AGENT_LLM_MODEL": "example-model",
}


def _ok(text: str = "ok interpretation"):
    def runner(argv, cwd, timeout, env=None):
        runner.calls.append({"argv": argv, "cwd": cwd, "timeout": timeout})
        return 0, text, ""

    runner.calls = []
    return runner


class TestJobAssistProfile(unittest.TestCase):
    def test_job_assist_one_call_after_telemetry(self) -> None:
        runner = _ok("rank imbalance likely")
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                [
                    "srun",
                    "--agent-profile=job-assist",
                    "--agent-output-dir",
                    tmp,
                    "-n",
                    "1",
                    "--",
                    "true",
                ]
            )
            seen: list[list[str]] = []

            def run_sidecar(argv: list[str]) -> int:
                seen.append(argv)
                joined = " ".join(argv)
                self.assertNotIn("secret-test", joined)
                self.assertIn("-u", joined)
                self.assertIn("ANTHROPIC_API_KEY", joined)
                return 0

            with patch("agent_sidecar.llm.chat_complete") as chat:
                code, run_dir, _plan = wrap_srun(
                    parsed,
                    env=dict(SECRET_ENV),
                    run_sidecar=run_sidecar,
                    run_user=lambda _a: 0,
                    opencode_runner=runner,
                )
                chat.assert_not_called()
            self.assertEqual(code, 0)
            self.assertEqual(len(runner.calls), 1)
            self.assertTrue((run_dir / "telemetry.json").is_file())
            prompt = runner.calls[0]["argv"][-1]
            self.assertIn("reason_code", prompt)
            self.assertEqual(runner.calls[0]["argv"][:3], ["opencode", "run", "--dir"])

    def test_tools_only_zero_calls(self) -> None:
        runner = _ok()
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
            wrap_srun(
                parsed,
                env=dict(SECRET_ENV),
                run_sidecar=lambda _a: 0,
                run_user=lambda _a: 0,
                opencode_runner=runner,
            )
            self.assertEqual(len(runner.calls), 0)

    def test_node_llm_does_not_start_node_model(self) -> None:
        runner = _ok()
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                [
                    "srun",
                    "--agent-profile=tools-only",
                    "--agent-node-llm",
                    "--agent-output-dir",
                    tmp,
                    "-n",
                    "1",
                    "--",
                    "true",
                ]
            )
            self.assertTrue(parsed.options.node_llm)
            sidecar: list[str] = []

            def run_sidecar(argv: list[str]) -> int:
                sidecar.extend(argv)
                return 0

            wrap_srun(
                parsed,
                env=dict(SECRET_ENV),
                run_sidecar=run_sidecar,
                run_user=lambda _a: 0,
                opencode_runner=runner,
            )
            self.assertEqual(len(runner.calls), 0)
            joined = " ".join(sidecar)
            self.assertIn("supervisor", joined)
            self.assertNotIn("node-llm", joined)
            self.assertNotIn("secret-test", joined)

    def test_cli_records_node_llm_unsupported(self) -> None:
        buf = StringIO()
        with patch("agent_sidecar.cli.cmd_srun", return_value=0):
            with patch("sys.stderr", buf):
                code = main(["srun", "--agent-node-llm", "-n", "1", "--", "true"])
        self.assertEqual(code, 0)
        self.assertIn("unsupported", buf.getvalue())

    def test_patches_job_assist_without_changing_reason(self) -> None:
        runner = _ok("maybe timeout instead")
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                [
                    "srun",
                    "--agent-profile=job-assist",
                    "--agent-output-dir",
                    tmp,
                    "-n",
                    "1",
                    "--",
                    "true",
                ]
            )

            def run_sidecar(argv: list[str]) -> int:
                out = Path(argv[argv.index("--output-dir") + 1])
                events = out / "events"
                events.mkdir(parents=True, exist_ok=True)
                (events / "stderr.tail").write_text("MPI_Abort\n", encoding="utf-8")
                return 0

            _code, run_dir, _plan = wrap_srun(
                parsed,
                env=dict(SECRET_ENV),
                run_sidecar=run_sidecar,
                run_user=lambda _a: 0,
                opencode_runner=runner,
            )
            doc = load_telemetry(run_dir)
            self.assertEqual(doc["reason_code"], "mpi_abort")
            self.assertTrue(doc.get("job_assist"))
            self.assertIn("assist/job.json", doc["evidence_paths"])
            self.assertTrue((run_dir / "assist" / "job.json").is_file())
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(note["suspected_reason"], "mpi_abort")
            self.assertEqual(note["actions"], [])
