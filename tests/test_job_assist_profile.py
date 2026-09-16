"""job-assist profile: wrap ends OpenCode with the user step."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(_Path(__file__).resolve().parent))

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from agent_fakes import NoPlot, NoWatch, RecWatch
from agent_sidecar.argv import parse_agent_argv
from agent_sidecar.cli import main
from agent_sidecar.live_opencode import ATTACH_HINT
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
    def test_wrap_final_opencode_by_default(self) -> None:
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
            code, run_dir, _plan = wrap_srun(
                parsed,
                env=dict(SECRET_ENV),
                run_sidecar=lambda _a: 0,
                run_user=lambda _a: 0,
                opencode_runner=runner,
                live_plotter=NoPlot(),
            )
            self.assertEqual(code, 0)
            self.assertEqual(len(runner.calls), 0)
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertIn("4. 建议", note["summary"])
            self.assertIn("--agent-match", note["summary"])
            self.assertEqual(note["actions"], [])
            doc = load_telemetry(run_dir)
            self.assertTrue(doc.get("job_assist"))

    def test_wrap_skips_final_opencode_when_timeout_zero(self) -> None:
        runner = _ok("should not run")
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
            code, run_dir, _plan = wrap_srun(
                parsed,
                env={**SECRET_ENV, "AGENT_OPENCODE_FINAL_TIMEOUT": "0"},
                run_sidecar=lambda _a: 0,
                run_user=lambda _a: 0,
                opencode_runner=runner,
                live_plotter=NoPlot(),
            )
            self.assertEqual(code, 0)
            self.assertEqual(len(runner.calls), 0)
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertIn("4. 建议", note["summary"])

    def test_wrap_final_opencode_when_timeout_set(self) -> None:
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
            code, run_dir, _plan = wrap_srun(
                parsed,
                env={**SECRET_ENV, "AGENT_OPENCODE_FINAL_TIMEOUT": "20"},
                run_sidecar=lambda _a: 0,
                run_user=lambda _a: 0,
                opencode_runner=runner,
                live_plotter=NoPlot(),
            )
            self.assertEqual(code, 0)
            self.assertEqual(len(runner.calls), 1)
            self.assertEqual(runner.calls[0]["timeout"], 20.0)
            self.assertTrue((run_dir / "assist" / "job.json").is_file())
            self.assertEqual(runner.calls[0]["argv"][:3], ["opencode", "run", "--dir"])
            self.assertIn("--auto", runner.calls[0]["argv"])

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
                    live_plotter=NoPlot(),
                )
                chat.assert_not_called()
            self.assertEqual(code, 0)
            self.assertEqual(len(runner.calls), 0)
            self.assertTrue((run_dir / "telemetry.json").is_file())
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertIn("4. 建议", note["summary"])

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
                live_plotter=NoPlot(),
            )
            self.assertEqual(len(runner.calls), 0)

    def test_omitted_profile_starts_tools_and_assist(self) -> None:
        runner = _ok("live default assist")
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                ["srun", "--agent-output-dir", tmp, "-n", "1", "--", "true"]
            )
            seen: list[list[str]] = []

            def run_sidecar(argv: list[str]) -> int:
                seen.append(argv)
                return 0

            code, run_dir, _plan = wrap_srun(
                parsed,
                env=dict(SECRET_ENV),
                run_sidecar=run_sidecar,
                run_user=lambda _a: 0,
                opencode_runner=runner,
                live_plotter=NoPlot(),
            )
            self.assertEqual(code, 0)
            self.assertEqual(parsed.options.profile, "job-assist")
            self.assertTrue(seen)
            self.assertIn("--overlap", seen[0])
            self.assertEqual(len(runner.calls), 0)
            self.assertTrue((run_dir / "telemetry.json").is_file())
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertIn("4. 建议", note["summary"])

    def test_non_tty_starts_watcher_before_user(self) -> None:
        runner = _ok()
        watch = RecWatch()
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                ["srun", "--agent-output-dir", tmp, "-n", "1", "--", "true"]
            )
            timeline: list[str] = []

            def run_sidecar(_argv: list[str]) -> int:
                timeline.append("sidecar")
                return 0

            def run_user(argv: list[str]) -> int:
                self.assertNotIn("opencode", argv)
                watch.order.append("user")
                return 0

            wrap_srun(
                parsed,
                env=dict(SECRET_ENV),
                run_sidecar=run_sidecar,
                run_user=run_user,
                opencode_runner=runner,
                live_plotter=NoPlot(),
                live_watcher=watch,
                tty=False,
            )
            self.assertEqual(timeline, ["sidecar"])
            self.assertEqual(watch.order, ["start", "user", "stop"])

    def test_tty_prints_attach_hint_without_stealing_srun(self) -> None:
        runner = _ok()
        watch = RecWatch()
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                ["srun", "--agent-output-dir", tmp, "-n", "1", "--", "true"]
            )
            buf = StringIO()

            def run_user(argv: list[str]) -> int:
                self.assertNotIn("opencode", argv)
                return 0

            with patch("sys.stderr", buf):
                wrap_srun(
                    parsed,
                    env={**SECRET_ENV, "AGENT_QUIET": "0"},
                    run_sidecar=lambda _a: 0,
                    run_user=run_user,
                    opencode_runner=runner,
                    live_plotter=NoPlot(),
                    live_watcher=watch,
                    tty=True,
                )
            self.assertIn(ATTACH_HINT, buf.getvalue())
            self.assertEqual(watch.order, ["start", "stop"])

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
                live_plotter=NoPlot(),
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
                env={**SECRET_ENV, "AGENT_OPENCODE_FINAL_TIMEOUT": "300"},
                run_sidecar=run_sidecar,
                run_user=lambda _a: 0,
                opencode_runner=runner,
                live_plotter=NoPlot(),
            )
            doc = load_telemetry(run_dir)
            self.assertEqual(doc["reason_code"], "mpi_abort")
            self.assertTrue(doc.get("job_assist"))
            self.assertIn("assist/job.json", doc["evidence_paths"])
            self.assertTrue((run_dir / "assist" / "job.json").is_file())
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(note["suspected_reason"], "mpi_abort")
            self.assertEqual(note["actions"], [])
            self.assertGreaterEqual(len(runner.calls), 1)

    def test_wrap_keeps_pack_note_without_opencode(self) -> None:
        runner = _ok("should not replace pack")
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
                run_user=lambda _a: 1,
                opencode_runner=runner,
                live_plotter=NoPlot(),
                live_watcher=NoWatch(),
            )
            self.assertEqual(len(runner.calls), 0)
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(note["suspected_reason"], "mpi_abort")
            self.assertIn("MPI", note["summary"])
            self.assertNotIn("should not replace pack", note["summary"])

    def test_live_file_does_not_overwrite_reason_final_after_telemetry(self) -> None:
        tel_seen: list[bool] = []
        run_holder: dict[str, Path] = {}

        class LiveWrite:
            def start(self, run_dir: Path) -> None:
                run_holder["dir"] = run_dir
                (run_dir / "assist" / "live.json").write_text(
                    json.dumps(
                        {
                            "host": "submit",
                            "summary": "live guessed timeout",
                            "suspected_reason": "timeout",
                            "actions": [],
                        }
                    ),
                    encoding="utf-8",
                )

            def tick(self) -> str:
                tel_seen.append((run_holder["dir"] / "telemetry.json").is_file())
                return "snap"

            def stop(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                ["srun", "--agent-output-dir", tmp, "-n", "1", "--", "true"]
            )

            def run_sidecar(argv: list[str]) -> int:
                out = Path(argv[argv.index("--output-dir") + 1])
                events = out / "events"
                events.mkdir(parents=True, exist_ok=True)
                (events / "stderr.tail").write_text("MPI_Abort\n", encoding="utf-8")
                return 0

            def tracking_runner(argv, cwd, timeout, env=None):
                tel_seen.append((run_holder["dir"] / "telemetry.json").is_file())
                return 0, "final ok", ""

            _code, run_dir, _plan = wrap_srun(
                parsed,
                env=dict(SECRET_ENV),
                run_sidecar=run_sidecar,
                run_user=lambda _a: 0,
                opencode_runner=tracking_runner,
                live_plotter=NoPlot(),
                live_watcher=LiveWrite(),
                tty=False,
            )
            doc = load_telemetry(run_dir)
            self.assertEqual(doc["reason_code"], "mpi_abort")
            live = json.loads((run_dir / "assist" / "live.json").read_text(encoding="utf-8"))
            self.assertEqual(live["suspected_reason"], "timeout")
            self.assertFalse(tel_seen)
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(note["suspected_reason"], "mpi_abort")
            self.assertIn("live guessed timeout", note["summary"])
            self.assertTrue(doc.get("job_assist"))
