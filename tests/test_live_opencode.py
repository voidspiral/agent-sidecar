"""Live OpenCode watcher: snapshots not JSONL bodies; injectable, no real binary."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sidecar.live_opencode import LiveWatcher, build_live_prompt
from agent_sidecar.telemetry import ensure_run_layout


SERIES_LINE = (
    '{"ts":1,"host":"h1","pid":9,"cpu_pct":40.0,"rss_mb":12.0,'
    '"io_read_bps":3.0,"io_write_bps":4.0}'
)


def _seed_series(run_dir: Path, extra: str = "") -> None:
    ensure_run_layout(run_dir)
    (run_dir / "series" / "h1_pid9.jsonl").write_text(
        SERIES_LINE + extra + "\n", encoding="utf-8"
    )
    (run_dir / "events" / "stderr.tail").write_text("MPI_Abort\n", encoding="utf-8")


class TestLiveOpencode(unittest.TestCase):
    def test_tick_prompt_is_snapshot_not_jsonl(self) -> None:
        calls: list[list[str]] = []

        def runner(argv, cwd, timeout, env=None):
            calls.append(argv)
            return 0, "ok", ""

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed_series(run_dir)
            watcher = LiveWatcher(opencode_runner=runner, interval=0)
            watcher.start(run_dir)
            prompt = watcher.tick()
            watcher.stop()
            watcher.stop()
            self.assertIsNotNone(prompt)
            self.assertIn("cpu_peak", prompt or "")
            self.assertIn("mpi_abort", prompt or "")
            self.assertNotIn(SERIES_LINE, prompt or "")
            _, _, snapshot = (prompt or "").partition("SNAPSHOT:")
            self.assertNotIn("/proc", snapshot)
            self.assertTrue(calls)
            self.assertIn("--auto", calls[0])
            self.assertIn("--format", calls[0])
            self.assertEqual(calls[0][:3], ["opencode", "run", "--dir"])
            self.assertIn("简体中文", prompt or "")

    def test_live_prompt_requires_chinese_summary(self) -> None:
        prompt = build_live_prompt({}, [], [], Path("/tmp/run"))
        self.assertIn("简体中文", prompt)
        self.assertIn("assist/live.json", prompt)
        self.assertIn("improvement suggestions", prompt)
        self.assertIn("分条", prompt)

    def test_tick_skips_empty_snapshot_without_opencode(self) -> None:
        calls: list[list[str]] = []

        def runner(argv, cwd, timeout, env=None):
            calls.append(argv)
            return 0, "ok", ""

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            watcher = LiveWatcher(opencode_runner=runner, interval=0)
            watcher.start(run_dir)
            self.assertIsNone(watcher.tick())
            self.assertEqual(calls, [])
            watcher.stop()

    def test_tick_skips_unchanged_snapshot(self) -> None:
        calls: list[list[str]] = []

        def runner(argv, cwd, timeout, env=None):
            calls.append(argv)
            return 0, "ok", ""

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed_series(run_dir)
            watcher = LiveWatcher(opencode_runner=runner, interval=0)
            watcher.start(run_dir)
            self.assertIsNotNone(watcher.tick())
            self.assertIsNone(watcher.tick())
            self.assertEqual(len(calls), 1)
            (run_dir / "series" / "h1_pid9.jsonl").write_text(
                SERIES_LINE + '\n{"ts":2,"host":"h1","pid":9,"cpu_pct":90.0,'
                '"rss_mb":12.0,"io_read_bps":3.0,"io_write_bps":4.0}\n',
                encoding="utf-8",
            )
            self.assertIsNotNone(watcher.tick())
            self.assertEqual(len(calls), 2)
            watcher.stop()

    def test_missing_opencode_is_fail_soft(self) -> None:
        def runner(argv, cwd, timeout, env=None):
            from agent_sidecar.opencode_assist import OpenCodeError

            raise OpenCodeError("opencode_missing", "opencode not on PATH")

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed_series(run_dir)
            watcher = LiveWatcher(opencode_runner=runner, interval=0)
            watcher.start(run_dir)
            watcher.tick()
            watcher.stop()
            err = run_dir / "events" / "opencode_missing.err"
            self.assertTrue(err.is_file())
            self.assertFalse((run_dir / "telemetry.json").is_file())

    def test_tick_timeout_keeps_written_live_note(self) -> None:
        from agent_sidecar.opencode_assist import OpenCodeError

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed_series(run_dir)

            def runner(argv, cwd, timeout, env=None):
                (run_dir / "assist").mkdir(parents=True, exist_ok=True)
                (run_dir / "assist" / "live.json").write_text(
                    json.dumps({"summary": "运行中采样正常。", "actions": []}),
                    encoding="utf-8",
                )
                raise OpenCodeError("opencode_timeout", "timed out")

            watcher = LiveWatcher(opencode_runner=runner, interval=0)
            watcher.start(run_dir)
            prompt = watcher.tick()
            watcher.stop()
            self.assertIsNotNone(prompt)
            self.assertFalse((run_dir / "events" / "opencode_timeout.err").is_file())
            note = json.loads((run_dir / "assist" / "live.json").read_text(encoding="utf-8"))
            self.assertIn("采样正常", note["summary"])
            self.assertEqual(note["actions"], [])
            raw = (run_dir / "assist" / "live.json").read_text(encoding="utf-8")
            self.assertIn("采样正常", raw)
            self.assertNotIn("\\u91c7", raw)

    def test_stop_cancels_in_flight_opencode(self) -> None:
        from agent_sidecar.opencode_assist import OpenCodeError

        started = threading.Event()

        def runner(argv, cwd, timeout, env=None, cancel=None, note_path=None):
            started.set()
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if cancel is not None and cancel.is_set():
                    raise OpenCodeError("opencode_cancelled", "opencode cancelled")
                time.sleep(0.05)
            raise OpenCodeError("opencode_timeout", "timed out")

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            _seed_series(run_dir)
            watcher = LiveWatcher(opencode_runner=runner, interval=0.05, timeout=30)
            watcher.start(run_dir)
            self.assertTrue(started.wait(2))
            t0 = time.monotonic()
            watcher.stop()
            self.assertLess(time.monotonic() - t0, 5)
            self.assertFalse((run_dir / "events" / "opencode_timeout.err").is_file())
            self.assertFalse((run_dir / "events" / "opencode_cancelled.err").is_file())

    def test_interval_from_env(self) -> None:
        with patch.dict(os.environ, {"AGENT_OPENCODE_LIVE_INTERVAL": "7.5"}):
            watcher = LiveWatcher(opencode_runner=lambda *_a, **_k: (0, "", ""), interval=None)
            self.assertEqual(watcher.interval, 7.5)
