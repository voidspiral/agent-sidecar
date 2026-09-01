"""sbatch exports agent env and does not rewrite the script."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from agent_sidecar.argv import AgentOptions
from agent_sidecar.run import sbatch_environ, submit_sbatch


class TestSbatchEnv(unittest.TestCase):
    def test_env_export_no_script_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "job.sh"
            original = "#!/bin/bash\nsrun ./app\n"
            script.write_text(original, encoding="utf-8")
            captured: dict[str, object] = {}

            def runner(argv: list[str], env: dict[str, str]) -> int:
                captured["argv"] = argv
                captured["env"] = env
                return 0

            options = AgentOptions(profile="tools-only", skills=("proc-monitor",), output_dir=str(Path(tmp) / "out"))
            code = submit_sbatch(script, options, runner=runner)
            self.assertEqual(code, 0)
            self.assertEqual(script.read_text(encoding="utf-8"), original)
            env = captured["env"]
            assert isinstance(env, dict)
            self.assertEqual(env["AGENT_PROFILE"], "tools-only")
            self.assertEqual(env["AGENT_SKILLS"], "proc-monitor")
            self.assertEqual(env["AGENT_JOB_DIR"], str(Path(tmp) / "out"))
            argv = captured["argv"]
            assert isinstance(argv, list)
            self.assertEqual(argv[0], "sbatch")
            self.assertEqual(argv[-1], str(script))
