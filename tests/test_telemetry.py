"""Telemetry schema tests."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import tempfile
import unittest
from pathlib import Path

from agent_sidecar.telemetry import retry_metadata, write_telemetry


class TestTelemetry(unittest.TestCase):
    def test_document_required_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            write_telemetry(
                run_dir,
                summary={"cpu_peak": 10.0},
                anomalies=[],
                evidence_paths=["meta.json"],
                reason_code="ok",
                retry_allowed=False,
                attempt=1,
            )
            doc = json.loads((run_dir / "telemetry.json").read_text(encoding="utf-8"))
            for key in ("summary", "anomalies", "evidence_paths", "reason_code"):
                self.assertIn(key, doc)
            self.assertEqual(doc["reason_code"], "ok")

    def test_application_nonzero_not_retried(self) -> None:
        meta = retry_metadata(user_exit=1, overlap_failed_before_start=False, attempt=1)
        self.assertFalse(meta["retry_allowed"])

    def test_overlap_fail_before_start_retry(self) -> None:
        meta = retry_metadata(user_exit=None, overlap_failed_before_start=True, attempt=1)
        self.assertTrue(meta["retry_allowed"])
        self.assertEqual(meta["attempt"], 1)
