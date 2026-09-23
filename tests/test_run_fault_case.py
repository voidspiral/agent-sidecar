"""run_fault_case.sh skips without srun; covers completed case ids."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_fault_case.sh"


class TestRunFaultCase(unittest.TestCase):
    def test_script_executable_and_documents_overrides(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(SCRIPT.stat().st_mode & stat.S_IXUSR)
        raw = SCRIPT.read_bytes()
        self.assertNotIn(b"\r", raw)
        text = raw.decode("utf-8")
        self.assertIn("assert_telemetry.py", text)
        self.assertIn("AGENT_OPENCODE_FINAL_TIMEOUT", text)
        self.assertIn("AGENT_BAD_PARTITION", text)
        self.assertIn("AGENT_CASE_MEM", text)
        self.assertIn("AGENT_CASE_TIME", text)
        self.assertIn("sidecar.sh", text)
        for case in ("01", "02", "03", "04", "05", "06", "06x", "07a", "10", "11a", "12", "13", "16"):
            with self.subTest(case=case):
                self.assertIn(case, text)

    def test_no_srun_exits_2(self) -> None:
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash not on PATH")
        empty = tempfile.mkdtemp()
        proc = subprocess.run(
            [bash, str(SCRIPT), "03"],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PATH": empty, "AGENT_ROOT": str(ROOT)},
        )
        self.assertEqual(proc.returncode, 2, proc.stderr + proc.stdout)
        self.assertIn("skip", (proc.stderr + proc.stdout).lower())

    def test_hardware_case_skips(self) -> None:
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash not on PATH")
        empty = tempfile.mkdtemp()
        # Put a fake srun on PATH so hardware skip is distinct from missing srun.
        fake = Path(empty) / "srun"
        fake.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
        fake.chmod(0o755)
        proc = subprocess.run(
            [bash, str(SCRIPT), "18"],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PATH": empty, "AGENT_ROOT": str(ROOT)},
        )
        self.assertEqual(proc.returncode, 2, proc.stderr + proc.stdout)
        self.assertIn("hardware", (proc.stderr + proc.stdout).lower())


if __name__ == "__main__":
    unittest.main()
