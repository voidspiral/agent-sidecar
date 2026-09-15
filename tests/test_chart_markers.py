"""Chart marker JSONL contract tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from agent_sidecar.chart_markers import (
    load_markers,
    marker_path,
    record_marker,
)
from agent_sidecar.spi import Event
from agent_sidecar.telemetry import ensure_run_layout


class TestChartMarkers(unittest.TestCase):
    def test_event_accepts_optional_ts(self) -> None:
        ev = Event(reason_code="mpi_abort", ts=12.5)
        self.assertEqual(ev.ts, 12.5)
        self.assertIsNone(Event(reason_code="mpi_abort").ts)

    def test_submit_host_writes_submit_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = ensure_run_layout(Path(tmp))
            wrote = record_marker(
                run_dir,
                reason_code="mpi_abort",
                host="submit",
                evidence_path="events/stderr.tail",
                message="mpi runtime fault",
                ts=10.0,
            )
            self.assertTrue(wrote)
            dest = run_dir / "events" / "submit_markers.jsonl"
            self.assertTrue(dest.is_file())
            rec = json.loads(dest.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(rec["reason_code"], "mpi_abort")
            self.assertEqual(rec["ts"], 10.0)
            self.assertEqual(rec["host"], "submit")
            self.assertEqual(rec["evidence_path"], "events/stderr.tail")

    def test_compute_host_writes_per_host_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = ensure_run_layout(Path(tmp))
            record_marker(
                run_dir,
                reason_code="node_local",
                host="cn1",
                evidence_path="events/node-diag.txt",
                ts=11.0,
            )
            record_marker(
                run_dir,
                reason_code="node_local",
                host="cn3",
                evidence_path="events/node-diag.txt",
                ts=12.0,
            )
            self.assertTrue(marker_path(run_dir, "cn1").is_file())
            self.assertTrue(marker_path(run_dir, "cn3").is_file())
            self.assertFalse((run_dir / "events" / "markers.jsonl").is_file())
            hosts = {m["host"] for m in load_markers(run_dir)}
            self.assertEqual(hosts, {"cn1", "cn3"})

    def test_duplicate_keeps_first_ts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = ensure_run_layout(Path(tmp))
            self.assertTrue(
                record_marker(
                    run_dir,
                    reason_code="slurm_oom",
                    host="cn1",
                    evidence_path="events/slurm.json",
                    ts=1.0,
                )
            )
            self.assertFalse(
                record_marker(
                    run_dir,
                    reason_code="slurm_oom",
                    host="cn1",
                    evidence_path="events/slurm.json",
                    ts=9.0,
                )
            )
            recs = load_markers(run_dir)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["ts"], 1.0)

    def test_unknown_code_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = ensure_run_layout(Path(tmp))
            self.assertFalse(
                record_marker(
                    run_dir,
                    reason_code="timeout",
                    host="cn1",
                    evidence_path="events/slurm.json",
                    ts=1.0,
                )
            )
            self.assertEqual(load_markers(run_dir), [])

    def test_anomalies_merge_ts_and_old_runs_omit_it(self) -> None:
        from agent_sidecar.telemetry import anomalies_from_artifacts, rollup_reason_code

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            events = run_dir / "events"
            events.mkdir()
            (events / "stderr.tail").write_text("MPI_Abort\n", encoding="utf-8")
            (events / "slurm.json").write_text(
                json.dumps({"JobState": "OUT_OF_MEMORY"}) + "\n", encoding="utf-8"
            )
            old = anomalies_from_artifacts(run_dir)
            self.assertTrue(all("ts" not in a for a in old))
            codes = [a["reason_code"] for a in old]
            self.assertEqual(rollup_reason_code(old, user_exit=1), codes[0])
            record_marker(
                run_dir,
                reason_code="mpi_abort",
                host="submit",
                evidence_path="events/stderr.tail",
                ts=42.0,
            )
            merged = anomalies_from_artifacts(run_dir)
            abort = [a for a in merged if a["reason_code"] == "mpi_abort"][0]
            self.assertEqual(abort["ts"], 42.0)
            self.assertEqual(
                rollup_reason_code(merged, user_exit=1),
                rollup_reason_code(old, user_exit=1),
            )
