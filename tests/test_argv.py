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

    def test_omitted_profile_is_job_assist(self) -> None:
        parsed = parse_agent_argv(["srun", "-n", "1", "hostname"])
        self.assertEqual(parsed.options.profile, "job-assist")
        self.assertTrue(parsed.options.quiet)

    def test_omitted_skills_enable_all_node_plugins(self) -> None:
        from agent_sidecar.argv import DEFAULT_SKILLS, apply_profile_defaults

        parsed = parse_agent_argv(["srun", "-n", "1", "--", "hostname"])
        apply_profile_defaults(parsed.options)
        self.assertEqual(
            parsed.options.skills,
            ("proc-monitor", "mpi-scan", "slurm-tap", "node-diag"),
        )
        self.assertEqual(parsed.options.skills, DEFAULT_SKILLS)

    def test_verbose_disables_default_quiet(self) -> None:
        from agent_sidecar.argv import agent_quiet

        parsed = parse_agent_argv(["srun", "--agent-verbose", "-n", "1", "--", "true"])
        self.assertTrue(parsed.options.verbose)
        self.assertFalse(agent_quiet(parsed.options, env={}))

    def test_explicit_tools_only_skips_default(self) -> None:
        parsed = parse_agent_argv(
            ["srun", "--agent-profile=tools-only", "-n", "1", "--", "./app"]
        )
        self.assertEqual(parsed.options.profile, "tools-only")

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

    def test_live_plot_flags(self) -> None:
        from agent_sidecar.argv import agent_live_plot

        on = parse_agent_argv(["srun", "--agent-live-plot", "-n", "1", "--", "true"])
        self.assertTrue(on.options.live_plot_cli)
        self.assertTrue(agent_live_plot(on.options, env={"AGENT_LIVE_PLOT": "0"}))
        off = parse_agent_argv(["srun", "--agent-no-live-plot", "-n", "1", "--", "true"])
        self.assertFalse(off.options.live_plot_cli)
        self.assertFalse(agent_live_plot(off.options, env={}))
        default = parse_agent_argv(["srun", "-n", "1", "--", "true"])
        self.assertIsNone(default.options.live_plot_cli)
        self.assertTrue(agent_live_plot(default.options, env={}))
        self.assertFalse(agent_live_plot(default.options, env={"AGENT_LIVE_PLOT": "0"}))

    def test_agent_match_flag(self) -> None:
        parsed = parse_agent_argv(
            [
                "srun",
                "--agent-match=mpi_io_load",
                "--agent-interval=0.5",
                "-n",
                "1",
                "--",
                "python3",
                "app.py",
            ]
        )
        self.assertEqual(parsed.options.match, "mpi_io_load")
        self.assertEqual(parsed.options.interval, 0.5)
        self.assertEqual(parsed.passthrough, ["-n", "1", "--", "python3", "app.py"])
