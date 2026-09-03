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

from agent_fakes import NoWatch, noop_opencode
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

    def test_format_run_report_includes_summary_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            ensure_run_layout(run_dir)
            (run_dir / "series" / "cn1_pid1.jsonl").write_text("{}\n", encoding="utf-8")
            (run_dir / "charts" / "cn1_pid1_cpu_pct.png").write_bytes(b"x")
            (run_dir / "assist" / "job.json").write_text(
                json.dumps({"summary": "作业成功", "actions": []}) + "\n",
                encoding="utf-8",
            )
            write_telemetry(
                run_dir,
                summary={
                    "host_count": 2,
                    "pid_count": 2,
                    "cpu_avg": 8.7,
                    "exit_code": 0,
                },
                anomalies=[],
                evidence_paths=["series/cn1_pid1.jsonl"],
                reason_code="ok",
                retry_allowed=False,
                attempt=1,
            )
            text = format_run_report(run_dir)
            self.assertIn("======== agent report ========", text)
            self.assertIn("reason_code: ok", text)
            self.assertIn("host_count: 2", text)
            self.assertIn("pid_count: 2", text)
            self.assertIn("series/cn1_pid1.jsonl", text)
            self.assertIn("charts/cn1_pid1_cpu_pct.png", text)
            self.assertIn("作业成功", text)
            path = write_run_report(run_dir)
            self.assertEqual(path, run_dir / "report.txt")
            self.assertTrue(path.is_file())

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
                    tty=False,
                )
            self.assertEqual(code, 0)
            text = buf.getvalue()
            self.assertIn("[agent] sidecar started", text)
            self.assertIn("[agent] user step started", text)
            self.assertIn("[agent] user exit=0", text)
            self.assertIn("======== agent report ========", text)
            self.assertIn("reason_code:", text)
            self.assertNotIn("passthrough=", text)
            self.assertNotIn("[agent] telemetry.json:", text)
            self.assertNotIn("start sidecar step:", text)
            reports = list(Path(tmp).glob("*/report.txt"))
            self.assertEqual(len(reports), 1)
