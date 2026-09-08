"""CLI exit code equals the wrapped command."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(_Path(__file__).resolve().parent))

import tempfile
import unittest
from pathlib import Path

from agent_fakes import NoPlot
from agent_sidecar.argv import parse_agent_argv
from agent_sidecar.run import wrap_srun


class TestExitCode(unittest.TestCase):
    def test_user_exit_preserved_with_collect_errors(self) -> None:
        parsed = parse_agent_argv(["srun", "--agent-output-dir", "X", "-n", "1", "--", "./app"])
        with tempfile.TemporaryDirectory() as tmp:
            parsed.options.output_dir = tmp

            def run_sidecar(_argv: list[str]) -> int:
                return 0

            def run_user(_argv: list[str]) -> int:
                return 7

            code, run_dir, _plan = wrap_srun(
                parsed,
                env={},
                run_sidecar=run_sidecar,
                run_user=run_user,
                collect_errors={"h1": "fetch timeout"},
                opencode_runner=lambda *a, **k: (0, "ok", ""),
                tty=False,
                live_plotter=NoPlot(),
            )
            self.assertEqual(code, 7)
            meta = (run_dir / "meta.json").read_text(encoding="utf-8")
            self.assertIn("fetch timeout", meta)
            self.assertTrue((run_dir / "telemetry.json").is_file())
