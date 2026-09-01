"""Classification tests."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import unittest

from agent_sidecar.classify import classify_mpi_text, classify_slurm_state


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
