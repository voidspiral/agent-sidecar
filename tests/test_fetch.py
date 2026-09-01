"""Fetch tests: copy artifacts, timeout does not hang."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from agent_sidecar.fetch import fetch_host_artifacts


class TestFetch(unittest.TestCase):
    def test_copy_local_temp_to_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote" / "series"
            remote.mkdir(parents=True)
            (remote / "h1_pid1.jsonl").write_text("{}\n", encoding="utf-8")
            local = root / "run"
            errors = fetch_host_artifacts("h1", root / "remote", local)
            self.assertEqual(errors, {})
            self.assertTrue((local / "series" / "h1_pid1.jsonl").is_file())

    def test_timeout_records_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "run"
            errors = fetch_host_artifacts(
                "h2",
                Path(tmp) / "missing",
                local,
                timeout=0.1,
                timed_out=True,
            )
            self.assertIn("h2", errors)
            self.assertIn("timeout", errors["h2"])
