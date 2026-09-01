"""Overlap failure falls back once to exec-wrapper."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import unittest

from agent_sidecar.launch import execute_launch, plan_overlap
from agent_sidecar.telemetry import retry_metadata


class TestLaunchFallback(unittest.TestCase):
    def test_overlap_fail_before_user_retries_exec_wrapper_once(self) -> None:
        plan = plan_overlap(["-n", "2", "--", "./app"], ["agent", "supervisor"])
        sidecar_calls: list[list[str]] = []
        user_calls: list[list[str]] = []

        def run_sidecar(argv: list[str]) -> int:
            sidecar_calls.append(argv)
            return 0

        def run_user(argv: list[str]) -> int:
            user_calls.append(argv)
            return 0

        code, used = execute_launch(
            plan,
            run_sidecar=run_sidecar,
            run_user=run_user,
            overlap_ok=False,
            passthrough=["-n", "2", "--", "./app"],
            wrap_argv=["agent", "exec-wrap"],
        )
        self.assertEqual(code, 0)
        self.assertEqual(sidecar_calls, [])
        self.assertEqual(len(user_calls), 1)
        self.assertTrue(used.fallback_used)
        self.assertEqual(used.mode, "exec-wrapper")
        self.assertIn("agent", used.user_argv)
        self.assertIn("exec-wrap", used.user_argv)
        meta = retry_metadata(user_exit=None, overlap_failed_before_start=True, attempt=1)
        self.assertTrue(meta["retry_allowed"])
        self.assertEqual(meta["attempt"], 1)

    def test_sidecar_nonzero_also_falls_back(self) -> None:
        plan = plan_overlap(["-n", "1", "--", "./app"], ["agent", "supervisor"])
        user_calls: list[list[str]] = []

        def run_sidecar(_argv: list[str]) -> int:
            return 1

        def run_user(argv: list[str]) -> int:
            user_calls.append(argv)
            return 0

        code, used = execute_launch(
            plan,
            run_sidecar=run_sidecar,
            run_user=run_user,
            overlap_ok=True,
            passthrough=["-n", "1", "--", "./app"],
            wrap_argv=["agent", "exec-wrap"],
        )
        self.assertEqual(code, 0)
        self.assertTrue(used.fallback_used)
        self.assertIn("exec-wrap", user_calls[0])
