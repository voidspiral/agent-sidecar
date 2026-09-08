"""Wrap starts/stops live plot beside the user step."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(_Path(__file__).resolve().parent))

import contextlib
import tempfile
import unittest
from pathlib import Path

from agent_fakes import FailPlot, NoWatch, RecPlot, RecWatch, noop_opencode
from agent_sidecar.argv import parse_agent_argv
from agent_sidecar.run import wrap_srun
from agent_sidecar.telemetry import load_telemetry


def _parsed(tmp: str, extra: list[str] | None = None):
    argv = ["srun", "--agent-profile=tools-only", "--agent-output-dir", tmp]
    if extra:
        argv.extend(extra)
    argv.extend(["-n", "1", "--", "true"])
    return parse_agent_argv(argv)


class TestLivePlotWrap(unittest.TestCase):
    def test_starts_before_user_and_stops_after(self) -> None:
        plot = RecPlot()
        watch = RecWatch()
        order: list[str] = []

        def run_user(_argv: list[str]) -> int:
            order.append("user")
            self.assertEqual(plot.order, ["start"])
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code, run_dir, _plan = wrap_srun(
                    _parsed(tmp),
                    env={},
                    run_sidecar=lambda _a: 0,
                    run_user=run_user,
                    live_watcher=watch,
                    live_plotter=plot,
                    tty=False,
                    opencode_runner=noop_opencode,
                )
            self.assertEqual(code, 0)
            self.assertEqual(plot.order, ["start", "stop"])
            self.assertEqual(order, ["user"])
            self.assertEqual(plot.run_dir, run_dir)
            self.assertIn("live plot: http://127.0.0.1:8765", err.getvalue())

    def test_no_live_plot_skips_start(self) -> None:
        plot = RecPlot()
        with tempfile.TemporaryDirectory() as tmp:
            code, _run_dir, _plan = wrap_srun(
                _parsed(tmp, ["--agent-no-live-plot"]),
                env={},
                run_sidecar=lambda _a: 0,
                run_user=lambda _a: 0,
                live_watcher=NoWatch(),
                live_plotter=plot,
                tty=False,
                opencode_runner=noop_opencode,
            )
            self.assertEqual(code, 0)
            self.assertEqual(plot.order, [])

    def test_bind_failure_is_fail_soft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, run_dir, _plan = wrap_srun(
                _parsed(tmp),
                env={},
                run_sidecar=lambda _a: 0,
                run_user=lambda _a: 0,
                live_watcher=NoWatch(),
                live_plotter=FailPlot(),
                tty=False,
                opencode_runner=noop_opencode,
            )
            self.assertEqual(code, 0)
            tel = load_telemetry(run_dir)
            self.assertIn("live_plot", tel.get("collect_errors") or {})
            self.assertEqual(tel["reason_code"], "ok")
