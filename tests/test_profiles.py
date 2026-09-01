"""Profile tests: default tools-only, unknown flags fail closed."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import unittest

from agent_sidecar.argv import AgentParseError, apply_profile_defaults, parse_agent_argv


class TestProfiles(unittest.TestCase):
    def test_omitted_profile_is_tools_only(self) -> None:
        parsed = parse_agent_argv(["srun", "-n", "1", "hostname"])
        apply_profile_defaults(parsed.options)
        self.assertEqual(parsed.options.profile, "tools-only")

    def test_unknown_agent_flag_exits_nonzero(self) -> None:
        with self.assertRaises(AgentParseError) as ctx:
            parse_agent_argv(["srun", "--agent-unknown=1", "-n", "1"])
        self.assertNotEqual(ctx.exception.exit_code, 0)

    def test_clusterhelm_profile_rejected(self) -> None:
        parsed = parse_agent_argv(["srun", "--agent-profile=clusterhelm", "-n", "1"])
        with self.assertRaises(AgentParseError) as ctx:
            apply_profile_defaults(parsed.options)
        self.assertNotEqual(ctx.exception.exit_code, 0)
        self.assertIn("clusterhelm", str(ctx.exception).lower())
