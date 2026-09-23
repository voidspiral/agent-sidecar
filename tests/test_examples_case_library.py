"""Case library dirs match 调研2 总表 IDs; 2a/2b share examples/02."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
# Padded 总表 IDs. 2a+2b → 02. 6x/7a/7b/11a/11b keep suffix.
CASES = (
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "06x",
    "07a",
    "07b",
    "08",
    "09",
    "10",
    "11a",
    "11b",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
)
DONE = {
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "06x",
    "07a",
    "10",
    "11a",
    "12",
    "13",
    "16",
}
HARDWARE = {"18", "19", "20", "21", "22", "23"}


class TestExamplesCaseLibrary(unittest.TestCase):
    def test_top_makefile_lists_every_case(self) -> None:
        text = (EXAMPLES / "Makefile").read_text(encoding="utf-8")
        self.assertIn("$(MAKE) -C $@", text)
        for case in CASES:
            with self.subTest(case=case):
                self.assertIn(case, text)

    def test_each_case_dir_has_empty_or_real_all_target(self) -> None:
        for case in CASES:
            makefile = EXAMPLES / case / "Makefile"
            with self.subTest(case=case):
                self.assertTrue(makefile.is_file(), f"missing {makefile}")
                body = makefile.read_text(encoding="utf-8")
                self.assertRegex(body, r"(?m)^all:")

    def test_02_merges_2a_and_2b(self) -> None:
        self.assertTrue((EXAMPLES / "02").is_dir())
        self.assertFalse((EXAMPLES / "02a").exists())
        self.assertFalse((EXAMPLES / "02b").exists())
        mk = (EXAMPLES / "02" / "Makefile").read_text(encoding="utf-8")
        self.assertRegex(mk, r"2a|2b|OOM")
        src = (EXAMPLES / "02" / "cgroup_oom.c").read_text(encoding="utf-8")
        self.assertIn("malloc", src)
        self.assertIn("unittest", src.lower() + mk.lower())

    def test_03_segfault_done(self) -> None:
        case = EXAMPLES / "03"
        self.assertTrue((case / "mpi_fault_segfault.c").is_file())
        self.assertTrue((case / "npb_cg_mid_segfault" / "build.sh").is_file())
        self.assertTrue((case / "npb_cg_mid_segfault" / "cg.f90.patch").is_file())
        mk = (case / "Makefile").read_text(encoding="utf-8")
        self.assertIn("mpi_fault_segfault", mk)
        self.assertIn("npb", mk)

    def test_06x_abort_done(self) -> None:
        case = EXAMPLES / "06x"
        self.assertTrue((case / "mpi_fault_abort.c").is_file())
        self.assertIn("mpi_fault_abort", (case / "Makefile").read_text(encoding="utf-8"))

    def test_10_launch_fail_done(self) -> None:
        case = EXAMPLES / "10"
        self.assertTrue((case / "launch_fail.sh").is_file())
        self.assertFalse((case / "no-such-mpi").exists())

    def test_01_missing_so_rpath(self) -> None:
        mk = (EXAMPLES / "01" / "Makefile").read_text(encoding="utf-8")
        self.assertIn("-Wl,-rpath", mk)
        self.assertIn("libmissing", mk)
        self.assertTrue((EXAMPLES / "01" / "mpi_missing_so.c").is_file())
        self.assertTrue((EXAMPLES / "01" / "missing.c").is_file())

    def test_04_job_sh_has_crlf(self) -> None:
        raw = (EXAMPLES / "04" / "job.sh").read_bytes()
        self.assertIn(b"\r\n", raw)
        mk = (EXAMPLES / "04" / "Makefile").read_text(encoding="utf-8")
        self.assertIn("job.sh", mk)

    def test_05_fpe_fixture(self) -> None:
        src = (EXAMPLES / "05" / "mpi_fault_fpe.c").read_text(encoding="utf-8")
        self.assertIn("SIGFPE", src)
        self.assertIn("rank %d fpe", src)
        mk = (EXAMPLES / "05" / "Makefile").read_text(encoding="utf-8")
        self.assertIn("mpi_fault_fpe", mk)

    def test_06_deadlock_fixture(self) -> None:
        src = (EXAMPLES / "06" / "mpi_fault_deadlock.c").read_text(encoding="utf-8")
        self.assertIn("rank %d deadlock", src)
        self.assertIn("MPI_Barrier", src)
        mk = (EXAMPLES / "06" / "Makefile").read_text(encoding="utf-8")
        self.assertIn("mpi_fault_deadlock", mk)

    def test_07a_enoent_fixture(self) -> None:
        src = (EXAMPLES / "07a" / "io_enoent.c").read_text(encoding="utf-8")
        self.assertIn("open", src)
        mk = (EXAMPLES / "07a" / "Makefile").read_text(encoding="utf-8")
        self.assertIn("io_enoent", mk)

    def test_11a_records_bad_partition(self) -> None:
        mk = (EXAMPLES / "11a" / "Makefile").read_text(encoding="utf-8")
        self.assertIn("__no_such_partition__", mk)
        self.assertIn("srun", mk)
        self.assertNotIn("mpicc", mk)

    def test_12_timeout_sleep(self) -> None:
        self.assertTrue((EXAMPLES / "12" / "sleep_timeout.sh").is_file())
        mk = (EXAMPLES / "12" / "Makefile").read_text(encoding="utf-8")
        self.assertIn("sleep_timeout", mk)

    def test_13_reuses_02_malloc(self) -> None:
        mk = (EXAMPLES / "13" / "Makefile").read_text(encoding="utf-8")
        self.assertIn("../02", mk)
        self.assertNotIn("malloc(", mk)

    def test_16_reuses_01_missing_so(self) -> None:
        mk = (EXAMPLES / "16" / "Makefile").read_text(encoding="utf-8")
        self.assertIn("../01", mk)
        self.assertTrue((EXAMPLES / "16" / "run_export_none.sh").is_file())
        script = (EXAMPLES / "16" / "run_export_none.sh").read_text(encoding="utf-8")
        self.assertRegex(script, r"export=NONE|LD_LIBRARY_PATH|unset")

    def test_hardware_18_23_remain_empty(self) -> None:
        for case in HARDWARE:
            body = (EXAMPLES / case / "Makefile").read_text(encoding="utf-8")
            with self.subTest(case=case):
                self.assertIn("@true", body)
                self.assertNotIn("mpicc", body)
                self.assertNotIn("cuda", body.lower())
                self.assertNotIn("scontrol", body)

    def test_incomplete_cases_have_noop_all(self) -> None:
        for case in CASES:
            if case in DONE:
                continue
            body = (EXAMPLES / case / "Makefile").read_text(encoding="utf-8")
            with self.subTest(case=case):
                self.assertNotIn("mpicc", body)
                self.assertRegex(body, r"(?m)^all:")

    def test_readme_has_sidecar_cookbook(self) -> None:
        text = (EXAMPLES / "README.md").read_text(encoding="utf-8")
        self.assertIn("sidecar.sh", text)
        self.assertIn("unset AGENT_OPENCODE_FINAL_TIMEOUT", text)
        self.assertIn("salloc -N2 -n2 -w cn[1-2] -p test", text)
        for needle in (
            "examples/01/mpi_missing_so",
            "examples/03/mpi_fault_segfault",
            "examples/05/mpi_fault_fpe",
            "examples/06/mpi_fault_deadlock",
            "examples/06x/mpi_fault_abort",
            "examples/10/no-such-mpi",
            "-p __no_such_partition__",
            "未实现",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_health_io_load_stays_at_examples_root(self) -> None:
        self.assertTrue((EXAMPLES / "mpi_io_load.c").is_file())
        self.assertFalse((EXAMPLES / "04" / "mpi_io_load.c").exists())
        self.assertIn("mpi_io_load", (EXAMPLES / "Makefile").read_text(encoding="utf-8"))

    def test_make_n_recurses(self) -> None:
        if shutil.which("make") is None:
            self.skipTest("make not on PATH")
        proc = subprocess.run(
            ["make", "-n", "-C", str(EXAMPLES)],
            capture_output=True,
            text=True,
            check=True,
        )
        out = proc.stdout + proc.stderr
        for case in CASES:
            with self.subTest(case=case):
                self.assertIn(case, out)

    def test_legacy_flat_fault_sources_removed(self) -> None:
        self.assertFalse((EXAMPLES / "mpi_fault_segfault.c").exists())
        self.assertFalse((EXAMPLES / "mpi_fault_abort.c").exists())
        self.assertFalse((EXAMPLES / "launch_fail.sh").exists())
        self.assertFalse((EXAMPLES / "npb_cg_mid_segfault").exists())


if __name__ == "__main__":
    unittest.main()
