"""Constructed abnormal states for every default sidecar plugin (no live SLURM)."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import tempfile
import unittest
from pathlib import Path

from agent_sidecar.argv import DEFAULT_SKILLS
from agent_sidecar.cli import _plugins_for
from agent_sidecar.spi import JobContext, reset_supervisors, start_supervisor
from agent_sidecar.telemetry import anomalies_from_artifacts
from agent_sidecar.tools.mpi_scan import MpiScan
from agent_sidecar.tools.node_diag import NodeDiag
from agent_sidecar.tools.proc_monitor import ProcMonitor
from agent_sidecar.tools.slurm_tap import SlurmTap


def _ctx(tmp: str, host: str = "h1") -> JobContext:
    return JobContext(job_id="123", host=host, output_dir=Path(tmp), match="app")


SLURM_CASES = (
    ("OUT_OF_MEMORY", "slurm_oom"),
    ("OOM", "slurm_oom"),
    ("NODE_FAIL", "node_fail"),
    ("TIMEOUT", "timeout"),
    ("CANCELLED", "cancelled"),
    ("CANCELED", "cancelled"),
    ("FAILED", "slurm_failed"),
    ("DEADLINE", "slurm_failed"),
    ("BOOT_FAIL", "slurm_failed"),
    ("PREEMPTED", "slurm_failed"),
)

MPI_CASES = (
    ("rank 0 called MPI_Abort(comm=MPI_COMM_WORLD, errorcode=1)", "mpi_abort"),
    ("PMIx abort: rank disconnected from daemon", "mpi_abort"),
    ("hydra: assert (!closed) failed", "mpi_abort"),
    ("disconnected rank 3 detected", "mpi_abort"),
    ("rank 0 segfault (null deref)", "mpi_segfault"),
    ("Segmentation fault", "mpi_segfault"),
    ("Rank 2 exited with signal 11", "mpi_segfault"),
)

NODE_DIAG_CASES = (
    ("Out of memory: Killed process 4242 (app) total-vm:100000kB", "node_local"),
    ("Killed process 9 (rank)", "node_local"),
)


class TestDefaultSkillsLoadAllPlugins(unittest.TestCase):
    def tearDown(self) -> None:
        reset_supervisors()

    def test_default_skills_are_all_node_plugins(self) -> None:
        self.assertEqual(
            DEFAULT_SKILLS,
            ("proc-monitor", "mpi-scan", "slurm-tap", "node-diag", "eth-monitor"),
        )

    def test_supervisor_starts_all_default_plugins_fail_soft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins = _plugins_for(DEFAULT_SKILLS)
            self.assertEqual([p.name for p in plugins], list(DEFAULT_SKILLS))
            ctx = JobContext(job_id="123", host="h1", output_dir=Path(tmp), match="")
            sup = start_supervisor("123", "h1", plugins, ctx)
            try:
                names = {p.name for p in plugins}
                self.assertEqual(names, set(DEFAULT_SKILLS))
            finally:
                sup.stop()


class TestSlurmTapAbnormalStates(unittest.TestCase):
    def test_each_scontrol_state(self) -> None:
        for state, expected in SLURM_CASES:
            with self.subTest(plugin="slurm-tap", state=state):
                with tempfile.TemporaryDirectory() as tmp:
                    ctx = _ctx(tmp)
                    text = (
                        f"JobId=123 JobName=app UserId=u(1000) JobState={state} "
                        f"NodeList=h1 ExitCode=1:0\n"
                    )
                    tool = SlurmTap(scontrol_text=text)
                    tool.start(ctx)
                    self.assertEqual(tool.events()[0].reason_code, expected)
                    snap = json.loads((Path(tmp) / "events" / "slurm.json").read_text(encoding="utf-8"))
                    self.assertEqual(snap["JobState"], state)
                    codes = [a["reason_code"] for a in anomalies_from_artifacts(Path(tmp))]
                    self.assertIn(expected, codes)

    def test_running_is_not_anomaly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool = SlurmTap(
                scontrol_text="JobId=123 JobState=RUNNING NodeList=h1 ExitCode=0:0\n"
            )
            tool.start(_ctx(tmp))
            self.assertEqual(tool.events(), [])
            self.assertEqual(anomalies_from_artifacts(Path(tmp)), [])


class TestMpiScanAbnormalStates(unittest.TestCase):
    def test_each_abort_pattern(self) -> None:
        for text, expected in MPI_CASES:
            with self.subTest(plugin="mpi-scan", text=text):
                with tempfile.TemporaryDirectory() as tmp:
                    tool = MpiScan(stderr_text=text + "\n")
                    tool.start(_ctx(tmp))
                    self.assertEqual(tool.events()[0].reason_code, expected)
                    tail = Path(tmp) / "events" / "stderr.tail"
                    self.assertTrue(tail.is_file())
                    self.assertIn(text.split()[0], tail.read_text(encoding="utf-8"))
                    codes = [a["reason_code"] for a in anomalies_from_artifacts(Path(tmp))]
                    self.assertIn(expected, codes)

    def test_clean_stderr_is_not_anomaly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool = MpiScan(stderr_text="all ranks completed\n")
            tool.start(_ctx(tmp))
            self.assertEqual(tool.events(), [])
            self.assertEqual(anomalies_from_artifacts(Path(tmp)), [])


class TestNodeDiagAbnormalStates(unittest.TestCase):
    def test_each_oom_trace(self) -> None:
        for text, expected in NODE_DIAG_CASES:
            with self.subTest(plugin="node-diag", text=text):
                with tempfile.TemporaryDirectory() as tmp:
                    tool = NodeDiag(dmesg_text=text)
                    tool.start(_ctx(tmp))
                    self.assertEqual(tool.events()[0].reason_code, expected)
                    snap = (Path(tmp) / "events" / "node-diag.txt").read_text(encoding="utf-8")
                    self.assertIn("oom_pids=", snap)
                    self.assertNotIn("oom_pids=[]", snap)
                    codes = [a["reason_code"] for a in anomalies_from_artifacts(Path(tmp))]
                    self.assertIn(expected, codes)

    def test_empty_dmesg_is_not_anomaly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool = NodeDiag(dmesg_text="")
            tool.start(_ctx(tmp))
            self.assertEqual(tool.events(), [])
            self.assertEqual(anomalies_from_artifacts(Path(tmp)), [])


class TestProcMonitorAbnormalStates(unittest.TestCase):
    def test_import_failure_is_collect_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool = ProcMonitor(loop_importer=lambda: (None, "no mpi_monitor"))
            tool.start(_ctx(tmp))
            tool.stop()
            err = Path(tmp) / "events" / "mpi_monitor_import.err"
            self.assertTrue(err.is_file())
            self.assertIn("no mpi_monitor", err.read_text(encoding="utf-8"))
            self.assertEqual(tool.events(), [])

    def test_empty_match_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = JobContext(job_id="123", host="h1", output_dir=Path(tmp), match="")
            tool = ProcMonitor(loop_importer=lambda: (None, None))
            tool.start(ctx)
            tool.stop()
            self.assertEqual(tool.events(), [])
