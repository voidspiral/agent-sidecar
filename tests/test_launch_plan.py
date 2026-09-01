"""Launch plan tests (stub srun)."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import unittest

from agent_sidecar.launch import plan_overlap


class TestLaunchPlan(unittest.TestCase):
    def test_default_overlap_and_separate_user_srun(self) -> None:
        plan = plan_overlap(
            ["-N", "2", "-n", "8", "--", "./app"],
            ["agent", "supervisor", "--job-id", "1", "--host", "%N"],
        )
        self.assertEqual(plan.mode, "overlap")
        self.assertIn("--overlap", plan.sidecar_argv)
        self.assertIn("--ntasks-per-node=1", plan.sidecar_argv)
        self.assertIn("--mem=256M", plan.sidecar_argv)
        self.assertIn("-l", plan.sidecar_argv)
        self.assertEqual(plan.user_argv[0], "srun")
        self.assertEqual(plan.user_argv[-1], "./app")
        self.assertNotEqual(plan.sidecar_argv, plan.user_argv)

    def test_never_bash_c_exec_user_step(self) -> None:
        plan = plan_overlap(["-n", "4", "--", "./app"], ["agent", "supervisor"])
        joined = " ".join(plan.user_argv)
        self.assertNotIn("bash -c", joined)
        self.assertNotIn("& exec", joined)
