"""slurm-tap tests on fixture text (no live scontrol/sacct)."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import tempfile
import unittest
from pathlib import Path

from agent_sidecar.spi import JobContext
from agent_sidecar.telemetry import anomalies_from_artifacts
from agent_sidecar.tools.slurm_tap import SlurmTap, parse_sacct, parse_scontrol


SCONTROL = """
JobId=123 JobName=app UserId=u(1000) JobState=OUT_OF_MEMORY NodeList=h1,h2 ExitCode=0:0
"""

SACCT = """
JobID|State|ExitCode|MaxRSS
123|NODE_FAIL|1:0|100K
"""

# Constructed scontrol snapshots. Tests inject this text; they do not exec scontrol.
ABNORMAL_SCONTROL = (
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


def _scontrol(state: str) -> str:
    return (
        f"JobId=123 JobName=app UserId=u(1000) JobState={state} "
        f"NodeList=h1,h2 ExitCode=1:0\n"
    )


def _start(tmp: str, *, scontrol_text: str = "", sacct_text: str = "") -> tuple[SlurmTap, Path]:
    run_dir = Path(tmp)
    ctx = JobContext(job_id="123", host="h1", output_dir=run_dir)
    tool = SlurmTap(scontrol_text=scontrol_text, sacct_text=sacct_text)
    tool.start(ctx)
    return tool, run_dir


class TestSlurmTap(unittest.TestCase):
    def test_parse_scontrol_oom(self) -> None:
        rec = parse_scontrol(SCONTROL)
        self.assertEqual(rec["JobId"], "123")
        self.assertEqual(rec["JobState"], "OUT_OF_MEMORY")
        self.assertEqual(rec["NodeList"], "h1,h2")

    def test_parse_sacct_node_fail(self) -> None:
        rec = parse_sacct(SACCT)
        self.assertEqual(rec["State"], "NODE_FAIL")

    def test_parse_sacct_prefers_timeout_step_over_running_job(self) -> None:
        rec = parse_sacct(
            "JobID|State|ExitCode|MaxRSS\n"
            "52|RUNNING|0:0|\n"
            "52.0|TIMEOUT|1:0|\n"
        )
        self.assertEqual(rec["State"], "TIMEOUT")
        self.assertEqual(rec["JobID"], "52.0")

    def test_running_alloc_plus_timeout_step_emits_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool, run_dir = _start(
                tmp,
                scontrol_text=_scontrol("RUNNING").replace("JobId=123", "JobId=52"),
                sacct_text=(
                    "JobID|State|ExitCode|MaxRSS\n"
                    "52|RUNNING|0:0|\n"
                    "52.0|TIMEOUT|1:0|\n"
                ),
            )
            self.assertEqual(tool.events()[0].reason_code, "timeout")
            snap = json.loads((run_dir / "events" / "slurm.json").read_text(encoding="utf-8"))
            self.assertEqual(snap["JobState"], "TIMEOUT")
            self.assertEqual(snap.get("AllocState"), "RUNNING")
            self.assertIn("timeout", [a["reason_code"] for a in anomalies_from_artifacts(run_dir)])

    def test_plugin_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool, run_dir = _start(tmp, scontrol_text=SCONTROL)
            self.assertEqual(tool.events()[0].reason_code, "slurm_oom")
            snap = run_dir / "events" / "slurm.json"
            self.assertTrue(snap.is_file())
            self.assertEqual(json.loads(snap.read_text(encoding="utf-8"))["JobState"], "OUT_OF_MEMORY")

    def test_constructed_abnormal_states_emit_events_and_anomalies(self) -> None:
        for state, expected in ABNORMAL_SCONTROL:
            with self.subTest(state=state), tempfile.TemporaryDirectory() as tmp:
                tool, run_dir = _start(tmp, scontrol_text=_scontrol(state))
                events = tool.events()
                self.assertEqual(len(events), 1, state)
                self.assertEqual(events[0].reason_code, expected, state)
                self.assertEqual(events[0].message, state)
                snap = json.loads((run_dir / "events" / "slurm.json").read_text(encoding="utf-8"))
                self.assertEqual(snap["JobState"], state)
                codes = [a["reason_code"] for a in anomalies_from_artifacts(run_dir)]
                self.assertIn(expected, codes, state)

    def test_constructed_sacct_node_fail_reaches_anomalies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool, run_dir = _start(tmp, sacct_text=SACCT)
            self.assertEqual(tool.events()[0].reason_code, "node_fail")
            snap = json.loads((run_dir / "events" / "slurm.json").read_text(encoding="utf-8"))
            self.assertEqual(snap["State"], "NODE_FAIL")
            codes = [a["reason_code"] for a in anomalies_from_artifacts(run_dir)]
            self.assertEqual(codes, ["node_fail"])

    def test_running_state_is_not_an_anomaly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool, run_dir = _start(tmp, scontrol_text=_scontrol("RUNNING"))
            self.assertEqual(tool.events(), [])
            self.assertEqual(anomalies_from_artifacts(run_dir), [])

    def test_empty_injection_writes_empty_snapshot(self) -> None:
        """Explicit empty fixture text; no state is invented and live collect is skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            tool, run_dir = _start(tmp, scontrol_text="")
            snap = json.loads((run_dir / "events" / "slurm.json").read_text(encoding="utf-8"))
            self.assertEqual(snap, {})
            self.assertEqual(tool.events(), [])
            self.assertEqual(anomalies_from_artifacts(run_dir), [])

    def test_live_collect_uses_job_id_and_writes_state(self) -> None:
        seen: list[str] = []

        def collect(job_id: str) -> tuple[str, str]:
            seen.append(job_id)
            return _scontrol("TIMEOUT"), ""

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ctx = JobContext(job_id="123", host="h1", output_dir=run_dir)
            tool = SlurmTap(collect=collect)
            tool.start(ctx)
            self.assertEqual(seen, ["123"])
            self.assertEqual(tool.events()[0].reason_code, "timeout")
            snap = json.loads((run_dir / "events" / "slurm.json").read_text(encoding="utf-8"))
            self.assertEqual(snap["JobState"], "TIMEOUT")
            self.assertIn("timeout", [a["reason_code"] for a in anomalies_from_artifacts(run_dir)])

    def test_stop_refreshes_live_snapshot(self) -> None:
        states = ["RUNNING", "OUT_OF_MEMORY"]

        def collect(_job_id: str) -> tuple[str, str]:
            return _scontrol(states.pop(0)), ""

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ctx = JobContext(job_id="123", host="h1", output_dir=run_dir)
            tool = SlurmTap(collect=collect)
            tool.start(ctx)
            self.assertEqual(tool.events(), [])
            tool.stop()
            self.assertEqual(tool.events()[0].reason_code, "slurm_oom")
            snap = json.loads((run_dir / "events" / "slurm.json").read_text(encoding="utf-8"))
            self.assertEqual(snap["JobState"], "OUT_OF_MEMORY")
            self.assertIn("slurm_oom", [a["reason_code"] for a in anomalies_from_artifacts(run_dir)])

    def test_injected_fixture_is_not_overwritten_on_stop(self) -> None:
        def collect(_job_id: str) -> tuple[str, str]:
            raise AssertionError("live collect must not run for fixture text")

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ctx = JobContext(job_id="123", host="h1", output_dir=run_dir)
            tool = SlurmTap(scontrol_text=_scontrol("TIMEOUT"), collect=collect)
            tool.start(ctx)
            tool.stop()
            self.assertEqual(tool.events()[0].reason_code, "timeout")

    def test_missing_scontrol_is_fail_soft(self) -> None:
        def collect(_job_id: str) -> tuple[str, str]:
            return "", ""

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ctx = JobContext(job_id="123", host="h1", output_dir=run_dir)
            tool = SlurmTap(collect=collect)
            tool.start(ctx)
            self.assertEqual(tool.events(), [])
            snap = json.loads((run_dir / "events" / "slurm.json").read_text(encoding="utf-8"))
            self.assertEqual(snap, {})
            err = run_dir / "events" / "slurm_tap.err"
            self.assertTrue(err.is_file())
            self.assertIn("scontrol", err.read_text(encoding="utf-8"))
