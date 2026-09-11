"""Login-host sidecar.sh / sidecar-analy.sh and AGENT_ENTRY profile default."""

from __future__ import annotations

import os
import stat
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_sidecar.argv import apply_profile_defaults, parse_agent_argv

ROOT = Path(__file__).resolve().parents[1]


class TestSidecarScripts(unittest.TestCase):
    def test_scripts_exist_executable_and_exec_module(self) -> None:
        for name in ("sidecar.sh", "sidecar-analy.sh"):
            path = ROOT / "scripts" / name
            self.assertTrue(path.is_file(), f"missing {path}")
            self.assertTrue(os.access(path, os.X_OK), f"not executable: {path}")
            text = path.read_text(encoding="utf-8")
            self.assertIn("PYTHONPATH", text)
            self.assertIn("python3 -m agent_sidecar", text)
            mode = path.stat().st_mode
            self.assertTrue(mode & stat.S_IXUSR)

    def test_sidecar_sh_sets_agent_entry(self) -> None:
        wrap = (ROOT / "scripts" / "sidecar.sh").read_text(encoding="utf-8")
        self.assertIn("AGENT_ENTRY=sidecar", wrap)
        analy = (ROOT / "scripts" / "sidecar-analy.sh").read_text(encoding="utf-8")
        self.assertNotIn("AGENT_ENTRY=sidecar", analy)

    def test_agent_entry_sidecar_defaults_tools_only(self) -> None:
        parsed = parse_agent_argv(["srun", "-n", "1", "--", "./app"])
        apply_profile_defaults(parsed.options, env={"AGENT_ENTRY": "sidecar"})
        self.assertEqual(parsed.options.profile, "tools-only")

    def test_agent_entry_explicit_job_assist_wins(self) -> None:
        parsed = parse_agent_argv(
            ["srun", "--agent-profile=job-assist", "-n", "1", "--", "./app"]
        )
        apply_profile_defaults(parsed.options, env={"AGENT_ENTRY": "sidecar"})
        self.assertEqual(parsed.options.profile, "job-assist")

    def test_module_srun_omit_profile_unchanged(self) -> None:
        parsed = parse_agent_argv(["srun", "-n", "1", "--", "./app"])
        apply_profile_defaults(parsed.options, env={})
        self.assertEqual(parsed.options.profile, "job-assist")

    def test_readmes_lead_with_two_scripts(self) -> None:
        for name in ("README.md", "README.zh.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("sidecar.sh srun", text, name)
            self.assertIn("sidecar-analy.sh --log", text, name)


if __name__ == "__main__":
    unittest.main()
