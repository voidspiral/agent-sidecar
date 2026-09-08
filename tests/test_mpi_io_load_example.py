"""Example mpi_io_load has an IO phase then an optional CPU phase."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "examples" / "mpi_io_load.c"


class TestMpiIoLoadExample(unittest.TestCase):
    def setUp(self) -> None:
        self.src = SRC.read_text(encoding="utf-8")

    def test_usage_documents_cpu_seconds_argv3(self) -> None:
        self.assertIn("[cpu_seconds]", self.src)
        self.assertIn("argv[3]", self.src)

    def test_unlinks_scratch_before_cpu_phase(self) -> None:
        unlink_at = self.src.find("unlink(path)")
        cpu_at = self.src.find("cpu_phase")
        self.assertGreater(unlink_at, 0)
        self.assertGreater(cpu_at, unlink_at)

    def test_rank0_logs_io_and_cpu_phase_markers(self) -> None:
        self.assertIn("io_phase done", self.src)
        self.assertIn("cpu_phase start", self.src)
        self.assertIn("cpu_phase done", self.src)

    def test_zero_cpu_seconds_skips_burn(self) -> None:
        self.assertIn("cpu_seconds", self.src)
        self.assertRegex(self.src, r"cpu_seconds\s*==\s*0|cpu_seconds\s*<=\s*0")


@unittest.skipUnless(
    os.environ.get("AGENT_TEST_MPI_COMPILE") == "1" and shutil.which("mpicc"),
    "set AGENT_TEST_MPI_COMPILE=1 with mpicc to enable",
)
class TestMpiIoLoadCompileRun(unittest.TestCase):
    def test_one_second_io_then_cpu_logs_phases(self) -> None:
        launcher = shutil.which("mpirun") or shutil.which("mpiexec")
        if launcher is None:
            self.skipTest("mpirun/mpiexec not on PATH")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            binary = work / "mpi_io_load"
            compile_cmd = ["mpicc", "-O2", "-Wall", "-Wextra", "-o", str(binary), str(SRC)]
            subprocess.run(compile_cmd, check=True, cwd=work, timeout=60)
            env = os.environ.copy()
            env.setdefault("OMPI_MCA_btl", "tcp,self")
            env.setdefault("OMPI_MCA_orte_keep_fqdn_hostnames", "true")
            proc = subprocess.run(
                [launcher, "--oversubscribe", "-n", "1", str(binary), "1", str(work), "1"],
                cwd=work,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            err = proc.stderr
            self.assertEqual(proc.returncode, 0, msg=err)
            self.assertIn("io_phase done", err)
            self.assertIn("cpu_phase start", err)
            self.assertIn("cpu_phase done", err)


if __name__ == "__main__":
    unittest.main()
