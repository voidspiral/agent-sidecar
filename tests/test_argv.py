"""Argv split: --agent-* consumed, remainder is SLURM."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import unittest

from agent_sidecar.argv import parse_agent_argv


class TestArgv(unittest.TestCase):
    def test_agent_flags_consumed_remainder_is_slurm(self) -> None:
        parsed = parse_agent_argv(
            [
                "srun",
                "--agent-profile=tools-only",
                "--agent-skills=proc-monitor,node-diag",
                "--agent-output-dir",
                "/tmp/runs",
                "--agent-node-llm",
                "-N",
                "2",
                "-n",
                "8",
                "--",
                "./app",
            ]
        )
        self.assertEqual(parsed.command, "srun")
        self.assertEqual(parsed.options.profile, "tools-only")
        self.assertEqual(parsed.options.skills, ("proc-monitor", "node-diag"))
        self.assertEqual(parsed.options.output_dir, "/tmp/runs")
        self.assertTrue(parsed.options.node_llm)
        self.assertEqual(parsed.passthrough, ["-N", "2", "-n", "8", "--", "./app"])
        self.assertNotIn("--agent-profile=tools-only", parsed.passthrough)
        self.assertNotIn("--agent-node-llm", parsed.passthrough)

    def test_verbose_flag_consumed(self) -> None:
        parsed = parse_agent_argv(
            ["srun", "--agent-verbose", "-n", "1", "hostname"]
        )
        self.assertTrue(parsed.options.verbose)
        self.assertEqual(parsed.passthrough, ["-n", "1", "hostname"])

    def test_equals_and_space_forms(self) -> None:
        parsed = parse_agent_argv(
            ["srun", "--agent-profile", "job-assist", "-n", "1", "hostname"]
        )
        self.assertEqual(parsed.options.profile, "job-assist")
        self.assertEqual(parsed.passthrough, ["-n", "1", "hostname"])
