"""Job-assist note writer and fail-soft OpenCode errors."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sidecar.assist import note_invokes_slurm, run_job_assist, write_job_assist_note
from agent_sidecar.opencode_assist import OpenCodeError
from agent_sidecar.telemetry import load_telemetry, write_telemetry


def _seed(run_dir: Path, *, reason: str = "mpi_abort", extra: dict | None = None) -> None:
    write_telemetry(
        run_dir,
        summary={"cpu_avg": 1.0, "exit_code": 1, "pid_count": 1},
        anomalies=[{"reason_code": reason, "message": "abort"}],
        evidence_paths=["events/stderr.tail"],
        reason_code=reason,
        retry_allowed=False,
        attempt=1,
        extra=extra or {"collect_errors": {}},
    )


def _ok_runner(text: str = "MPI abort on rank 0; consider scancel the leftover step"):
    def runner(argv, cwd, timeout, env=None):
        runner.calls.append({"argv": argv, "cwd": cwd, "timeout": timeout, "env": env})
        return 0, text, ""

    runner.calls = []
    return runner


class TestJobAssist(unittest.TestCase):
    def test_successful_note_copies_reason_and_empty_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir)
            runner = _ok_runner()
            code = run_job_assist(run_dir, opencode_runner=runner, user_exit=9)
            self.assertEqual(code, 9)
            self.assertEqual(len(runner.calls), 1)
            argv = runner.calls[0]["argv"]
            self.assertEqual(argv[:3], ["opencode", "run", "--dir"])
            self.assertIn("--auto", argv)
            self.assertIn("--agent", argv)
            path = run_dir / "assist" / "job.json"
            self.assertTrue(path.is_file())
            note = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(note["host"], "submit")
            self.assertEqual(note["suspected_reason"], "mpi_abort")
            self.assertEqual(note["actions"], [])
            self.assertFalse(note_invokes_slurm(note))
            blob = path.read_text(encoding="utf-8")
            self.assertNotIn('"scancel"', blob)
            self.assertNotIn('"scontrol"', blob)
            self.assertIn("--format", argv)
            self.assertIn("json", argv)
            doc = load_telemetry(run_dir)
            self.assertEqual(doc["reason_code"], "mpi_abort")

    def test_write_note_keeps_raw_chinese(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_job_assist_note(
                run_dir,
                reason_code="ok",
                summary="1. 结论：作业成功。",
                evidence_paths=[],
            )
            raw = (run_dir / "assist" / "job.json").read_text(encoding="utf-8")
            self.assertIn("结论", raw)
            self.assertNotIn("\\u7ed3", raw)

    def test_write_note_forces_empty_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            path = write_job_assist_note(
                run_dir,
                reason_code="slurm_oom",
                summary="OOM; scancel recommended",
                evidence_paths=["events/slurm.json"],
            )
            note = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(note["actions"], [])
            self.assertEqual(note["suspected_reason"], "slurm_oom")

    def test_missing_opencode_records_and_no_http(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir, reason="ok")

            def runner(argv, cwd, timeout, env=None):
                raise OpenCodeError("opencode_missing", "opencode not on PATH")

            with patch("agent_sidecar.llm.chat_complete") as chat:
                code = run_job_assist(run_dir, opencode_runner=runner, user_exit=3)
                chat.assert_not_called()
            self.assertEqual(code, 3)
            doc = load_telemetry(run_dir)
            self.assertIn("opencode_missing", doc["collect_errors"])
            self.assertEqual(doc["reason_code"], "ok")
            self.assertFalse((run_dir / "assist" / "job.json").is_file())

    def test_nonzero_records_and_keeps_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir)

            def runner(argv, cwd, timeout, env=None):
                return 2, "", "opencode boom"

            code = run_job_assist(run_dir, opencode_runner=runner, user_exit=4)
            self.assertEqual(code, 4)
            doc = load_telemetry(run_dir)
            self.assertIn("opencode_failed", doc["collect_errors"])
            self.assertEqual(doc["reason_code"], "mpi_abort")

    def test_timeout_records_and_keeps_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir)

            def runner(argv, cwd, timeout, env=None):
                raise OpenCodeError("opencode_timeout", "timed out")

            code = run_job_assist(run_dir, opencode_runner=runner, user_exit=5)
            self.assertEqual(code, 5)
            doc = load_telemetry(run_dir)
            self.assertIn("opencode_timeout", doc["collect_errors"])
            self.assertEqual(doc["reason_code"], "mpi_abort")

    def test_timeout_keeps_written_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir)

            def runner(argv, cwd, timeout, env=None):
                write_job_assist_note(
                    run_dir,
                    reason_code="mpi_abort",
                    summary="作业已结束，采样正常。",
                    evidence_paths=["events/stderr.tail"],
                )
                raise OpenCodeError("opencode_timeout", "timed out")

            code = run_job_assist(run_dir, opencode_runner=runner, user_exit=5)
            self.assertEqual(code, 5)
            doc = load_telemetry(run_dir)
            self.assertNotIn("opencode_timeout", doc.get("collect_errors") or {})
            self.assertEqual(doc["reason_code"], "mpi_abort")
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertIn("作业已结束", note["summary"])
            self.assertEqual(note["actions"], [])
            self.assertIn("assist/job.json", doc.get("evidence_paths") or [])

    def test_prompt_does_not_embed_jsonl_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            series_line = '{"ts":1,"host":"h1","pid":9,"cpu_pct":99.0}'
            write_telemetry(
                run_dir,
                summary={"cpu_avg": 1.0, "pid_count": 1},
                anomalies=[],
                evidence_paths=["series/h1_pid9.jsonl"],
                reason_code="ok",
                retry_allowed=False,
                attempt=1,
                extra={"collect_errors": {}},
            )
            (run_dir / "series").mkdir(exist_ok=True)
            (run_dir / "series" / "h1_pid9.jsonl").write_text(series_line + "\n")
            runner = _ok_runner("ok interpretation")
            run_job_assist(run_dir, opencode_runner=runner, user_exit=0)
            prompt = runner.calls[0]["argv"][-1]
            self.assertIn("reason_code", prompt)
            self.assertNotIn(series_line, prompt)
            self.assertIn("series/h1_pid9.jsonl", prompt)

    def test_promotes_live_json_and_skips_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir, reason="mpi_abort")
            assist = run_dir / "assist"
            assist.mkdir(exist_ok=True)
            (assist / "live.json").write_text(
                json.dumps(
                    {
                        "host": "submit",
                        "summary": "1. 结论：作业中途 MPI abort。",
                        "suspected_reason": "timeout",
                        "actions": [],
                    }
                ),
                encoding="utf-8",
            )
            runner = _ok_runner()
            code = run_job_assist(run_dir, opencode_runner=runner, user_exit=7)
            self.assertEqual(code, 7)
            self.assertEqual(len(runner.calls), 0)
            note = json.loads((run_dir / "assist" / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(note["suspected_reason"], "mpi_abort")
            self.assertIn("MPI abort", note["summary"])
            doc = load_telemetry(run_dir)
            self.assertEqual(doc["reason_code"], "mpi_abort")
            self.assertIn("assist/job.json", doc.get("evidence_paths") or [])

    def test_skips_final_opencode_when_timeout_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir, reason="ok")
            runner = _ok_runner()
            code = run_job_assist(
                run_dir,
                opencode_runner=runner,
                user_exit=0,
                timeout=0,
            )
            self.assertEqual(code, 0)
            self.assertEqual(len(runner.calls), 0)
            self.assertFalse((run_dir / "assist" / "job.json").is_file())

    def test_final_timeout_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir, reason="ok")
            runner = _ok_runner()
            code = run_job_assist(
                run_dir,
                opencode_runner=runner,
                user_exit=0,
                env={"AGENT_OPENCODE_FINAL_TIMEOUT": "0"},
            )
            self.assertEqual(code, 0)
            self.assertEqual(len(runner.calls), 0)
