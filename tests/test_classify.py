"""Classification tests."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import unittest

from agent_sidecar.analysis.packs import select_pack
from agent_sidecar.classify import classify_mpi_text, classify_node_diag_text, classify_slurm_state


class TestClassify(unittest.TestCase):
    def test_slurm_states(self) -> None:
        self.assertEqual(classify_slurm_state("OUT_OF_MEMORY"), "slurm_oom")
        self.assertEqual(classify_slurm_state("NODE_FAIL"), "node_fail")
        self.assertEqual(classify_slurm_state("TIMEOUT"), "timeout")
        self.assertEqual(classify_slurm_state("CANCELLED"), "cancelled")
        self.assertEqual(classify_slurm_state("FAILED"), "slurm_failed")
        self.assertIsNone(classify_slurm_state("COMPLETED"))

    def test_mpi_abort_patterns(self) -> None:
        self.assertEqual(classify_mpi_text("rank 3 called MPI_Abort"), "mpi_abort")
        self.assertEqual(classify_mpi_text("PMIx abort: rank disconnected"), "mpi_abort")
        self.assertEqual(classify_mpi_text("assert (!closed)"), "mpi_abort")
        self.assertIsNone(classify_mpi_text("job finished ok"))

    def test_mpi_segfault_patterns(self) -> None:
        self.assertEqual(
            classify_mpi_text("rank 0 segfault (null deref)"), "mpi_segfault"
        )
        self.assertEqual(classify_mpi_text("Segmentation fault"), "mpi_segfault")
        self.assertEqual(classify_mpi_text("*** Process received signal 11 ***"), "mpi_segfault")
        self.assertEqual(classify_mpi_text("Rank 1 exited on signal 11 (SIGSEGV)"), "mpi_segfault")
        self.assertEqual(classify_mpi_text("rank 3 called MPI_Abort"), "mpi_abort")

    def test_mpi_fpe_patterns(self) -> None:
        self.assertEqual(classify_mpi_text("rank 0 fpe (SIGFPE)"), "mpi_fpe")
        self.assertEqual(classify_mpi_text("Floating point exception"), "mpi_fpe")
        self.assertEqual(classify_mpi_text("Process received SIGFPE"), "mpi_fpe")
        self.assertEqual(classify_mpi_text("Rank 1 exited on signal 8"), "mpi_fpe")
        self.assertEqual(classify_mpi_text("rank 3 called MPI_Abort"), "mpi_abort")

    def test_mpi_deadlock_patterns(self) -> None:
        self.assertEqual(
            classify_mpi_text("rank 0 deadlock (skip barrier)"), "mpi_deadlock"
        )
        self.assertEqual(classify_mpi_text("rank 3 called MPI_Abort"), "mpi_abort")

    def test_fpe_and_deadlock_use_stub_pack(self) -> None:
        self.assertEqual(select_pack("mpi_fpe", {"pid_count": 2}), "stub")
        self.assertEqual(select_pack("mpi_deadlock", {"pid_count": 2}), "stub")
        self.assertEqual(select_pack("slurm_oom", {"pid_count": 1}), "stub")

    def test_node_diag_snapshot(self) -> None:
        self.assertEqual(classify_node_diag_text("oom_pids=[9]\noom_kill=0\n"), "node_local")
        self.assertEqual(classify_node_diag_text("oom_pids=[]\noom_kill=1\n"), "node_local")
        self.assertIsNone(classify_node_diag_text("oom_pids=[]\noom_kill=0\nfs_hang_lines=0\n"))
