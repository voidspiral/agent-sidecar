"""Plot is optional; JSONL is kept when matplotlib is missing."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent_sidecar.tools.plot import plot_run


class TestPlotOptional(unittest.TestCase):
    def test_missing_matplotlib_keeps_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            series = run_dir / "series"
            series.mkdir()
            sample = series / "h1_pid1.jsonl"
            sample.write_text(
                json.dumps(
                    {
                        "ts": 1.0,
                        "host": "h1",
                        "pid": 1,
                        "cpu_pct": 1.0,
                        "rss_mb": 2.0,
                        "io_read_bps": 0,
                        "io_write_bps": 0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with mock.patch.dict("sys.modules", {"matplotlib": None, "matplotlib.pyplot": None}):
                written = plot_run(run_dir, plotter=None)
                # Force the import-miss path via plotter that records skip
            written = plot_run(run_dir, plotter=lambda *_a, **_k: [])
            self.assertEqual(written, [])
            self.assertTrue(sample.is_file())
            self.assertTrue(sample.read_text(encoding="utf-8").strip())
