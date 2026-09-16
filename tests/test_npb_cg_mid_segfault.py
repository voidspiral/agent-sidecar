"""NPB CG mid-run segfault example patch and build helper."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "examples" / "npb_cg_mid_segfault" / "cg.f90.patch"
BUILD = ROOT / "examples" / "npb_cg_mid_segfault" / "build.sh"
SNIPPET_CG = ROOT / "tests" / "fixtures" / "npb_cg_loop.f90"
CANDIDATE_NPB = (
    Path(os.environ["NPB_MPI_ROOT"])
    if os.environ.get("NPB_MPI_ROOT")
    else Path("/home/voidspiral/NPB3.4.3/NPB3.4-MPI")
)


def _apply(cg_src: Path, dest_root: Path) -> Path:
    cg_dir = dest_root / "CG"
    cg_dir.mkdir(parents=True)
    dest = cg_dir / "cg.f90"
    shutil.copyfile(cg_src, dest)
    proc = subprocess.run(
        ["patch", "-p1", "-i", str(PATCH)],
        cwd=dest_root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stdout + proc.stderr)
    return dest


class TestNpbCgMidSegfault(unittest.TestCase):
    def test_patch_file_exists(self) -> None:
        self.assertTrue(PATCH.is_file(), f"missing {PATCH}")

    def test_patch_applies_to_loop_snippet(self) -> None:
        self.assertTrue(SNIPPET_CG.is_file())
        with tempfile.TemporaryDirectory() as tmp:
            patched = _apply(SNIPPET_CG, Path(tmp))
            text = patched.read_text(encoding="utf-8")
        self.assertIn("crash_t0 = mpi_wtime()", text)
        self.assertIn("(mpi_wtime() - crash_t0) .ge. 30.0d0", text)
        self.assertNotIn("timer_read(1) .ge. 30.0d0", text)
        self.assertIn("me .eq. 0", text)
        self.assertIn("write(0, '(a)') 'rank 0 segfault (null deref)'", text)
        self.assertIn("c_null_ptr", text)
        self.assertIn("call sleep(3)", text)
        self.assertIn("call c_exit(0_c_int)", text)

    @unittest.skipUnless(
        (CANDIDATE_NPB / "CG" / "cg.f90").is_file(),
        "NPB 3.4-MPI tree not present",
    )
    def test_patch_applies_to_npb_343_cg(self) -> None:
        src = CANDIDATE_NPB / "CG" / "cg.f90"
        with tempfile.TemporaryDirectory() as tmp:
            patched = _apply(src, Path(tmp))
            text = patched.read_text(encoding="utf-8")
        self.assertIn("crash_t0 = mpi_wtime()", text)
        self.assertIn("(mpi_wtime() - crash_t0) .ge. 30.0d0", text)
        self.assertNotIn("timer_read(1) .ge. 30.0d0", text)
        self.assertIn("rank 0 segfault (null deref)", text)
        self.assertIn("call c_exit(0_c_int)", text)

    def test_build_requires_npb_mpi_root(self) -> None:
        self.assertTrue(BUILD.is_file())
        env = os.environ.copy()
        env.pop("NPB_MPI_ROOT", None)
        proc = subprocess.run(
            ["bash", str(BUILD)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(ROOT),
        )
        self.assertNotEqual(proc.returncode, 0)
        combined = proc.stdout + proc.stderr
        self.assertIn("NPB_MPI_ROOT", combined)
