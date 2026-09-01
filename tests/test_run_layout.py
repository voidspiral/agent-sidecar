"""Run directory layout tests."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from agent_sidecar.telemetry import ensure_run_layout, write_meta, write_telemetry


class TestRunLayout(unittest.TestCase):
    def test_layout_and_no_home_literals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "out" / "run1"
            ensure_run_layout(run_dir)
            write_meta(run_dir, {"hosts": ["h1"]})
            write_telemetry(
                run_dir,
                summary={},
                anomalies=[],
                evidence_paths=[],
                reason_code="ok",
                retry_allowed=False,
                attempt=1,
            )
            self.assertTrue((run_dir / "telemetry.json").is_file())
            self.assertTrue((run_dir / "meta.json").is_file())
            self.assertTrue((run_dir / "series").is_dir())
            self.assertTrue((run_dir / "assist").is_dir())
            src = Path(__file__).resolve().parents[1] / "src"
            text = (src / "agent_sidecar" / "telemetry.py").read_text(encoding="utf-8")
            self.assertNotIn("/home/" + "smt", text)
            self.assertNotIn("/home/" + "cn1", text)
