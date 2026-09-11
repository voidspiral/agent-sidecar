"""Quiet mode: key steps only, then a final artifact report."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(_Path(__file__).resolve().parent))

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agent_fakes import NoPlot, NoWatch, noop_opencode
from agent_sidecar.argv import parse_agent_argv
from agent_sidecar.cli import cmd_srun
from agent_sidecar.report import format_run_report, write_run_report
from agent_sidecar.telemetry import ensure_run_layout, write_telemetry


class TestQuietReport(unittest.TestCase):
    def test_defaults_quiet_proc_monitor_and_job_dir(self) -> None:
        from agent_sidecar.argv import apply_profile_defaults
        from agent_sidecar.run import resolve_output_dir

        parsed = parse_agent_argv(["srun", "-n", "1", "--", "true"])
        apply_profile_defaults(parsed.options)
        self.assertTrue(parsed.options.quiet)
        self.assertEqual(
            parsed.options.skills,
            ("proc-monitor", "mpi-scan", "slurm-tap", "node-diag"),
        )
        env = {}
        got = resolve_output_dir(parsed.options, env)
        if Path("/shared").is_dir():
            self.assertEqual(got, Path("/shared/agent-runs"))
        else:
            self.assertEqual(got, Path("runs"))
        parsed = parse_agent_argv(
            ["srun", "--agent-quiet", "-n", "1", "--", "true"]
        )
        self.assertTrue(parsed.options.quiet)
        self.assertEqual(parsed.passthrough, ["-n", "1", "--", "true"])

    def _seed_run(
        self,
        run_dir: Path,
        *,
        series: tuple[str, ...] = ("cn1_pid1.jsonl",),
        charts: tuple[str, ...] = ("cn1_pid1_cpu_pct.png",),
        assist_summary: str | None = "作业成功",
        events: tuple[str, ...] = (),
        summary: dict | None = None,
        reason_code: str = "ok",
        extra: dict | None = None,
    ) -> None:
        ensure_run_layout(run_dir)
        for name in series:
            (run_dir / "series" / name).write_text("{}\n", encoding="utf-8")
        for name in charts:
            (run_dir / "charts" / name).write_bytes(b"x")
        for name in events:
            (run_dir / "events" / name).write_text("e\n", encoding="utf-8")
        if assist_summary is not None:
            (run_dir / "assist" / "job.json").write_text(
                json.dumps({"summary": assist_summary, "actions": []}) + "\n",
                encoding="utf-8",
            )
        write_telemetry(
            run_dir,
            summary=summary
            or {
                "host_count": 2,
                "pid_count": 2,
                "cpu_avg": 8.7,
                "cpu_peak": 92,
                "rss_peak_mb": 412,
                "io_read_bps_sum": 100,
                "io_write_bps_sum": 200,
                "exit_code": 0,
            },
            anomalies=[],
            evidence_paths=["series/cn1_pid1.jsonl"],
            reason_code=reason_code,
            retry_allowed=False,
            attempt=1,
            extra=extra,
        )

    def test_format_run_report_includes_summary_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._seed_run(run_dir)
            text = format_run_report(run_dir)
            self.assertIn("======== agent report ========", text)
            self.assertIn(f"run:    {run_dir}", text)
            self.assertIn("exit:   0    reason: ok    hosts: 2    pids: 2", text)
            self.assertIn("作业成功", text)
            self.assertLess(text.index("作业成功"), text.index("evidence"))
            self.assertIn("metrics  cpu avg/peak 8.7/92  rss_peak_mb 412  io_r/w 100/200", text)
            self.assertIn("  cn1  pid 1", text)
            self.assertIn("evidence  series/×1  charts/×1", text)
            self.assertIn("assist/job.json", text)
            self.assertNotIn("charts/cn1_pid1_cpu_pct.png", text)
            self.assertNotIn("collect_errors", text)
            self.assertNotIn("host_count:", text)
            self.assertNotIn("sidecar-analy.sh", text)
            path = write_run_report(run_dir)
            self.assertEqual(path, run_dir / "report.txt")
            self.assertTrue(path.is_file())

    def test_format_run_report_non_ok_suggests_sidecar_analy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._seed_run(
                run_dir,
                reason_code="mpi_abort",
                summary={
                    "host_count": 1,
                    "pid_count": 1,
                    "exit_code": 1,
                },
            )
            text = format_run_report(run_dir)
            self.assertIn("sidecar-analy.sh", text)
            self.assertIn("--log", text)
            self.assertIn(str(run_dir), text)
            self.assertIn("--code", text)

    def test_format_run_report_omits_empty_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._seed_run(run_dir, assist_summary=None)
            text = format_run_report(run_dir)
            self.assertNotIn("collect_errors", text)
            self.assertNotIn("\nerrors\n", text)

    def test_format_run_report_lists_collect_errors_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._seed_run(
                run_dir,
                extra={"collect_errors": {"opencode_missing": "no binary"}},
            )
            text = format_run_report(run_dir)
            self.assertIn("errors", text)
            self.assertIn("opencode_missing: no binary", text)

    def test_format_run_report_collapses_charts_and_groups_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._seed_run(
                run_dir,
                series=("cn2_pid9.jsonl", "cn1_pid2.jsonl", "cn1_pid1.jsonl"),
                charts=(
                    "cn1_pid1_cpu_pct.png",
                    "cn1_pid1_rss_mb.png",
                    "cn1_pid2_cpu_pct.png",
                    "cn2_pid9_cpu_pct.png",
                ),
                events=("stderr.tail",),
                summary={
                    "host_count": 2,
                    "pid_count": 3,
                    "exit_code": 0,
                },
            )
            text = format_run_report(run_dir)
            self.assertIn("hosts: 2    pids: 3", text)
            self.assertIn("  cn1  pid 1, 2", text)
            self.assertIn("  cn2  pid 9", text)
            self.assertIn("charts/×4", text)
            self.assertIn("series/×3", text)
            self.assertIn("events/stderr.tail", text)
            self.assertNotIn(".png", text)
            self.assertLess(text.index("  cn1  pid 1, 2"), text.index("  cn2  pid 9"))

    def test_format_run_report_puts_job_assist_before_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._seed_run(
                run_dir,
                assist_summary="1. 结论：成功\n2. 采集：hosts=2",
            )
            text = format_run_report(run_dir)
            self.assertLess(text.index("1. 结论：成功"), text.index("metrics"))
            self.assertLess(text.index("1. 结论：成功"), text.index("evidence"))

    def test_quiet_srun_prints_key_steps_and_report_not_verbose_dump(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_agent_argv(
                [
                    "srun",
                    "--agent-quiet",
                    "--agent-profile=tools-only",
                    "--agent-output-dir",
                    tmp,
                    "-n",
                    "1",
                    "--",
                    "true",
                ]
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cmd_srun(
                    parsed,
                    run_sidecar=lambda _a: 0,
                    run_user=lambda _a: 0,
                    opencode_runner=noop_opencode,
                    live_watcher=NoWatch(),
                    live_plotter=NoPlot(),
                    tty=False,
                )
            self.assertEqual(code, 0)
            text = buf.getvalue()
            self.assertIn("[agent] sidecar started", text)
            self.assertIn("[agent] user step started", text)
            self.assertIn("[agent] user exit=0", text)
            self.assertIn("======== agent report ========", text)
            self.assertIn("reason:", text)
            self.assertNotIn("metrics", text)
            self.assertNotIn("passthrough=", text)
            self.assertNotIn("[agent] telemetry.json:", text)
            self.assertNotIn("start sidecar step:", text)
            reports = list(Path(tmp).glob("*/report.txt"))
            self.assertEqual(len(reports), 1)
