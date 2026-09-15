"""mpi-scan tests."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from agent_sidecar.spi import JobContext
from agent_sidecar.tools.mpi_scan import MpiScan, scan_stderr


class TestMpiScan(unittest.TestCase):
    def test_abort_vs_clean(self) -> None:
        self.assertEqual(scan_stderr("rank 0 MPI_Abort(comm, 1)"), "mpi_abort")
        self.assertIsNone(scan_stderr("all ranks completed"))

    def test_segfault_patterns(self) -> None:
        self.assertEqual(scan_stderr("rank 0 segfault (null deref)"), "mpi_segfault")
        self.assertEqual(scan_stderr("*** Signal 11 ***"), "mpi_segfault")

    def test_plugin_emits_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = JobContext(job_id="1", host="h1", output_dir=Path(tmp))
            tool = MpiScan(stderr_text="fatal: MPI_Abort from rank 2\n")
            tool.start(ctx)
            ev = tool.events()
            self.assertEqual(ev[0].reason_code, "mpi_abort")
            self.assertIsInstance(ev[0].ts, float)
            self.assertTrue(ev[0].evidence_path)
            marker = Path(tmp) / "events" / "h1_markers.jsonl"
            self.assertTrue(marker.is_file())

    def test_plugin_emits_segfault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = JobContext(job_id="1", host="h1", output_dir=Path(tmp))
            tool = MpiScan(stderr_text="rank 1 segfault (null deref)\n")
            tool.start(ctx)
            ev = tool.events()
            self.assertEqual(ev[0].reason_code, "mpi_segfault")
            self.assertTrue(ev[0].evidence_path)
