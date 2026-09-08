"""Wrap-end JobTelemetry aggregates series and tool artifacts."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(_Path(__file__).resolve().parent))

import json
import tempfile
import unittest
from pathlib import Path

from agent_fakes import NoPlot, NoWatch, noop_opencode
from agent_sidecar.argv import parse_agent_argv
from agent_sidecar.run import wrap_srun
from agent_sidecar.telemetry import load_telemetry


def _wrap(tmp: str, *, populate):
    parsed = parse_agent_argv(
        ["srun", "--agent-output-dir", tmp, "-n", "1", "--", "true"]
    )

    def run_sidecar(argv: list[str]) -> int:
        out = Path(argv[argv.index("--output-dir") + 1])
        populate(out)
        return 0

    code, run_dir, _plan = wrap_srun(
        parsed,
        env={},
        run_sidecar=run_sidecar,
        run_user=lambda _argv: 0,
        opencode_runner=noop_opencode,
        live_watcher=NoWatch(), live_plotter=NoPlot(),
        tty=False,
    )
    return code, run_dir


class TestWrapTelemetry(unittest.TestCase):
    def test_summary_from_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:

            def populate(out: Path) -> None:
                series = out / "series"
                series.mkdir(parents=True, exist_ok=True)
                (series / "h1_pid10.jsonl").write_text(
                    json.dumps(
                        {
                            "ts": 1,
                            "host": "h1",
                            "pid": 10,
                            "cpu_pct": 10.0,
                            "rss_mb": 100.0,
                            "io_read_bps": 8.0,
                            "io_write_bps": 4.0,
                        }
                    )
                    + "\n"
                    + json.dumps(
                        {
                            "ts": 2,
                            "host": "h1",
                            "pid": 10,
                            "cpu_pct": 30.0,
                            "rss_mb": 200.0,
                            "io_read_bps": 2.0,
                            "io_write_bps": 6.0,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

            code, run_dir = _wrap(tmp, populate=populate)
            self.assertEqual(code, 0)
            doc = load_telemetry(run_dir)
            self.assertTrue((run_dir / ".agent-stop").is_file())
            summary = doc["summary"]
            for key in (
                "cpu_avg",
                "cpu_peak",
                "rss_peak_mb",
                "io_read_bps_sum",
                "io_write_bps_sum",
                "host_count",
                "pid_count",
            ):
                self.assertIn(key, summary)
            self.assertEqual(summary["cpu_avg"], 20.0)
            self.assertEqual(summary["cpu_peak"], 30.0)
            self.assertEqual(summary["rss_peak_mb"], 200.0)
            self.assertEqual(summary["io_read_bps_sum"], 10.0)
            self.assertEqual(summary["io_write_bps_sum"], 10.0)
            self.assertEqual(summary["host_count"], 1)
            self.assertEqual(summary["pid_count"], 1)

    def test_empty_series_uses_nulls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, run_dir = _wrap(tmp, populate=lambda _out: None)
            self.assertEqual(code, 0)
            summary = load_telemetry(run_dir)["summary"]
            self.assertIsNone(summary["cpu_avg"])
            self.assertIsNone(summary["cpu_peak"])
            self.assertIsNone(summary["rss_peak_mb"])
            self.assertEqual(summary["host_count"], 0)
            self.assertEqual(summary["pid_count"], 0)

    def test_events_become_anomalies_and_reason_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:

            def populate(out: Path) -> None:
                events = out / "events"
                events.mkdir(parents=True, exist_ok=True)
                (events / "stderr.tail").write_text(
                    "rank 0: MPI_Abort(comm=MPI_COMM_WORLD, errorcode=1)\n",
                    encoding="utf-8",
                )
                (events / "slurm.json").write_text(
                    json.dumps({"JobState": "OUT_OF_MEMORY"}) + "\n",
                    encoding="utf-8",
                )

            code, run_dir = _wrap(tmp, populate=populate)
            self.assertEqual(code, 0)
            doc = load_telemetry(run_dir)
            codes = [a["reason_code"] for a in doc["anomalies"]]
            self.assertIn("mpi_abort", codes)
            self.assertIn("slurm_oom", codes)
            self.assertIn(doc["reason_code"], codes)
            self.assertNotEqual(doc["reason_code"], "ok")

    def test_plotter_paths_listed_in_evidence(self) -> None:
        written: list[Path] = []

        def populate(out: Path) -> None:
            series = out / "series"
            series.mkdir(parents=True, exist_ok=True)
            (series / "h1_pid10.jsonl").write_text(
                json.dumps(
                    {
                        "ts": 1,
                        "host": "h1",
                        "pid": 10,
                        "cpu_pct": 1.0,
                        "rss_mb": 2.0,
                        "io_read_bps": 0,
                        "io_write_bps": 0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

        def plotter(jsonl_path: Path, charts_dir: Path) -> list[Path]:
            charts_dir.mkdir(parents=True, exist_ok=True)
            dest = charts_dir / f"{jsonl_path.stem}_cpu_pct.png"
            dest.write_bytes(b"png")
            written.append(dest)
            return [dest]

        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                ["srun", "--agent-output-dir", tmp, "-n", "1", "--", "true"]
            )
            code, run_dir, _plan = wrap_srun(
                parsed,
                env={},
                run_sidecar=lambda argv: populate(Path(argv[argv.index("--output-dir") + 1])) or 0,
                run_user=lambda _a: 0,
                plotter=plotter,
                opencode_runner=noop_opencode,
                live_watcher=NoWatch(), live_plotter=NoPlot(),
                tty=False,
            )
            self.assertEqual(code, 0)
            self.assertTrue(written)
            doc = load_telemetry(run_dir)
            self.assertIn("charts/h1_pid10_cpu_pct.png", doc["evidence_paths"])
            self.assertTrue((run_dir / "charts" / "h1_pid10_cpu_pct.png").is_file())

    def test_mpi_monitor_import_error_keeps_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:

            def populate(out: Path) -> None:
                events = out / "events"
                events.mkdir(parents=True, exist_ok=True)
                (events / "mpi_monitor_import.err").write_text("cannot import\n")

            code, run_dir = _wrap(tmp, populate=populate)
            self.assertEqual(code, 0)
            doc = load_telemetry(run_dir)
            self.assertIn("mpi_monitor_import", doc["collect_errors"])
            self.assertEqual(doc["reason_code"], "ok")

    def test_supervisor_argv_includes_match_and_interval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                [
                    "srun",
                    "--agent-output-dir",
                    tmp,
                    "-n",
                    "1",
                    "--",
                    "/shared/agent-sidecar/examples/mpi_io_load",
                    "60",
                ]
            )
            seen: list[str] = []

            def run_sidecar(argv: list[str]) -> int:
                seen.extend(argv)
                return 0

            wrap_srun(
                parsed,
                env={},
                run_sidecar=run_sidecar,
                run_user=lambda _a: 0,
                opencode_runner=noop_opencode,
                live_watcher=NoWatch(), live_plotter=NoPlot(),
                tty=False,
            )
            self.assertIn("--match", seen)
            self.assertEqual(seen[seen.index("--match") + 1], "mpi_io_load")
            self.assertIn("--interval", seen)

    def test_agent_match_overrides_basename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                [
                    "srun",
                    "--agent-match=mpi_io_load",
                    "--agent-output-dir",
                    tmp,
                    "-n",
                    "1",
                    "--",
                    "python3",
                    "app.py",
                ]
            )
            seen: list[str] = []

            def run_sidecar(argv: list[str]) -> int:
                seen.extend(argv)
                return 0

            wrap_srun(
                parsed,
                env={},
                run_sidecar=run_sidecar,
                run_user=lambda _a: 0,
                opencode_runner=noop_opencode,
                live_watcher=NoWatch(), live_plotter=NoPlot(),
                tty=False,
            )
            self.assertEqual(seen[seen.index("--match") + 1], "mpi_io_load")

    def test_wrap_refreshes_slurm_step_timeout_after_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                ["srun", "--agent-output-dir", tmp, "-n", "1", "--", "true"]
            )

            def collect(job_id: str) -> tuple[str, str]:
                self.assertEqual(job_id, "52")
                return (
                    "JobId=52 JobState=RUNNING NodeList=cn[1-3] ExitCode=0:0\n",
                    "JobID|State|ExitCode|MaxRSS\n52|RUNNING|0:0|\n52.0|TIMEOUT|1:0|\n",
                )

            code, run_dir, _plan = wrap_srun(
                parsed,
                env={"SLURM_JOB_ID": "52"},
                run_sidecar=lambda _a: 0,
                run_user=lambda _a: 1,
                opencode_runner=noop_opencode,
                live_watcher=NoWatch(), live_plotter=NoPlot(),
                tty=False,
                slurm_collect=collect,
            )
            self.assertEqual(code, 1)
            snap = json.loads((run_dir / "events" / "slurm.json").read_text(encoding="utf-8"))
            self.assertEqual(snap["JobState"], "TIMEOUT")
            doc = load_telemetry(run_dir)
            self.assertIn("timeout", [a["reason_code"] for a in doc["anomalies"]])
            self.assertEqual(doc["reason_code"], "timeout")

    def test_wrap_captures_mpi_abort_from_user_stdio(self) -> None:
        from agent_sidecar.run import run_user_command

        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                ["srun", "--agent-output-dir", tmp, "-n", "1", "--", "true"]
            )

            def run_user(_argv: list[str]) -> int:
                return run_user_command(
                    [
                        sys.executable,
                        "-c",
                        "import sys; sys.stderr.write('rank 0 MPI_Abort\\n'); sys.exit(1)",
                    ]
                )

            code, run_dir, _plan = wrap_srun(
                parsed,
                env={},
                run_sidecar=lambda _a: 0,
                run_user=run_user,
                opencode_runner=noop_opencode,
                live_watcher=NoWatch(), live_plotter=NoPlot(),
                tty=False,
            )
            self.assertEqual(code, 1)
            tail = (run_dir / "events" / "stderr.tail").read_text(encoding="utf-8")
            self.assertIn("MPI_Abort", tail)
            doc = load_telemetry(run_dir)
            self.assertIn("mpi_abort", [a["reason_code"] for a in doc["anomalies"]])
            self.assertEqual(doc["reason_code"], "mpi_abort")
