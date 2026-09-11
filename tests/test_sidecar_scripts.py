"""Login-host sidecar.sh / sidecar-analy.sh; wrap defaults to job-assist."""

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

    def test_sidecar_sh_does_not_force_tools_only(self) -> None:
        wrap = (ROOT / "scripts" / "sidecar.sh").read_text(encoding="utf-8")
        self.assertNotIn("AGENT_ENTRY=sidecar", wrap)
        self.assertIn("exec python3 -m agent_sidecar", wrap)

    def test_sidecar_sh_usage_puts_agent_flags_before_srun(self) -> None:
        wrap = (ROOT / "scripts" / "sidecar.sh").read_text(encoding="utf-8")
        self.assertIn("sidecar.sh [--agent-*] srun", wrap)
        self.assertNotIn("srun [ --agent-* ]", wrap)

    def test_sidecar_sh_omit_profile_is_job_assist(self) -> None:
        parsed = parse_agent_argv(["srun", "-n", "1", "--", "./app"])
        apply_profile_defaults(parsed.options, env={})
        self.assertEqual(parsed.options.profile, "job-assist")

    def test_explicit_tools_only_still_opts_out(self) -> None:
        parsed = parse_agent_argv(
            ["srun", "--agent-profile=tools-only", "-n", "1", "--", "./app"]
        )
        apply_profile_defaults(parsed.options, env={})
        self.assertEqual(parsed.options.profile, "tools-only")

    def test_readmes_lead_with_two_scripts(self) -> None:
        for name in ("README.md", "README.zh.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("sidecar.sh srun", text, name)
            self.assertIn("sidecar-analy.sh --log", text, name)

    def test_cluster_notes_use_native_srun_tail(self) -> None:
        notes = ROOT / "测试.md"
        self.assertTrue(notes.is_file(), notes)
        text = notes.read_text(encoding="utf-8")
        self.assertIn("sidecar.sh [--agent-*] srun", text)
        self.assertIn("sidecar.sh --agent-verbose srun -n2", text)
        self.assertIn("sidecar.sh srun -n2", text)
        self.assertNotIn("--agent-match=", text)
        self.assertNotIn("srun -n2 --", text)


if __name__ == "__main__":
    unittest.main()
