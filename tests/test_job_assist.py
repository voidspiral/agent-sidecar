"""Job-assist note writer and fail-soft model errors."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import tempfile
import unittest
from pathlib import Path

from agent_sidecar.assist import note_invokes_slurm, run_job_assist, write_job_assist_note
from agent_sidecar.llm import LlmConfig, LlmError
from agent_sidecar.telemetry import load_telemetry, write_telemetry


def _seed(run_dir: Path, *, reason: str = "mpi_abort", extra: dict | None = None) -> None:
    write_telemetry(
        run_dir,
        summary={"cpu_avg": 1.0, "exit_code": 1},
        anomalies=[{"reason_code": reason, "message": "abort"}],
        evidence_paths=["events/stderr.tail"],
        reason_code=reason,
        retry_allowed=False,
        attempt=1,
        extra=extra or {"collect_errors": {}},
    )


class TestJobAssist(unittest.TestCase):
    def test_successful_note_copies_reason_and_empty_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir)
            cfg = LlmConfig(base_url="https://api.example.com/v1", api_key="k", model="m")

            def transport(_url, _headers, _body, _timeout):
                return 200, json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "MPI abort on rank 0; consider scancel the leftover step"
                                }
                            }
                        ]
                    }
                ).encode("utf-8")

            code = run_job_assist(run_dir, cfg=cfg, transport=transport, user_exit=9)
            self.assertEqual(code, 9)
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
            doc = load_telemetry(run_dir)
            self.assertEqual(doc["reason_code"], "mpi_abort")

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

    def test_missing_key_records_unconfigured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir, reason="ok")
            cfg = LlmConfig(base_url="https://api.example.com/v1", api_key="", model="m")
            code = run_job_assist(run_dir, cfg=cfg, user_exit=3)
            self.assertEqual(code, 3)
            doc = load_telemetry(run_dir)
            self.assertIn("llm_unconfigured", doc["collect_errors"])
            self.assertEqual(doc["reason_code"], "ok")
            self.assertFalse((run_dir / "assist" / "job.json").is_file())

    def test_http_error_records_and_keeps_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir)
            cfg = LlmConfig(base_url="https://api.example.com/v1", api_key="k", model="m")
            code = run_job_assist(
                run_dir,
                cfg=cfg,
                transport=lambda *_a, **_k: (502, b"bad"),
                user_exit=4,
            )
            self.assertEqual(code, 4)
            doc = load_telemetry(run_dir)
            self.assertIn("llm_http", doc["collect_errors"])
            self.assertEqual(doc["reason_code"], "mpi_abort")

    def test_timeout_records_and_keeps_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir)

            def transport(_url, _headers, _body, _timeout):
                raise LlmError("llm_timeout", "timed out")

            cfg = LlmConfig(base_url="https://api.example.com/v1", api_key="k", model="m")
            code = run_job_assist(run_dir, cfg=cfg, transport=transport, user_exit=5)
            self.assertEqual(code, 5)
            doc = load_telemetry(run_dir)
            self.assertIn("llm_timeout", doc["collect_errors"])
            self.assertEqual(doc["reason_code"], "mpi_abort")

    def test_parse_failure_records_and_keeps_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed(run_dir)
            cfg = LlmConfig(base_url="https://api.example.com/v1", api_key="k", model="m")
            code = run_job_assist(
                run_dir,
                cfg=cfg,
                transport=lambda *_a, **_k: (200, b"not-json"),
                user_exit=6,
            )
            self.assertEqual(code, 6)
            doc = load_telemetry(run_dir)
            self.assertIn("llm_parse", doc["collect_errors"])
            self.assertEqual(doc["reason_code"], "mpi_abort")
