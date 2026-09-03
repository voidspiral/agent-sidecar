"""node-diag tests (OOM / cgroup fixtures and live collect)."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from agent_sidecar.classify import classify_node_diag_text
from agent_sidecar.spi import JobContext
from agent_sidecar.telemetry import anomalies_from_artifacts
from agent_sidecar.tools.node_diag import (
    NodeDiag,
    NodeSnapshot,
    default_node_collect,
    find_job_cgroup,
    parse_cgroup_procs,
    parse_fs_hang,
    parse_kmsg,
    parse_oom_kill,
    parse_oom_trace,
    parse_proc_cgroup,
)


def _ctx(tmp: str, host: str = "h1") -> JobContext:
    return JobContext(job_id="123", host=host, output_dir=Path(tmp), match="app")


def _cgroup_tree(root: Path, *, oom_kill: int = 0, procs: str = "10\n11\n") -> Path:
    job = root / "sys" / "fs" / "cgroup" / "slurm" / "uid_1000" / "job_123"
    job.mkdir(parents=True)
    (job / "cgroup.procs").write_text(procs, encoding="utf-8")
    (job / "memory.events").write_text(f"low 0\noom 0\noom_kill {oom_kill}\n", encoding="utf-8")
    return job


class TestNodeDiagParse(unittest.TestCase):
    def test_oom_and_cgroup_parse(self) -> None:
        dmesg = "Out of memory: Killed process 4242 (app) total-vm:100000kB"
        self.assertEqual(parse_oom_trace(dmesg), [4242])
        self.assertEqual(parse_cgroup_procs("10\n11\n"), [10, 11])

    def test_oom_kill_memcg_pid(self) -> None:
        line = (
            "oom-kill:constraint=CONSTRAINT_MEMCG,nodemask=(null),"
            "task=app,pid=4242,uid=1000"
        )
        self.assertEqual(parse_oom_trace(line), [4242])

    def test_parse_oom_kill_skips_disable(self) -> None:
        v1 = "oom_kill_disable 0\nunder_oom 0\noom_kill 3\n"
        self.assertEqual(parse_oom_kill(v1), 3)
        v2 = "low 0\noom 0\noom_kill 1\noom_group_kill 0\n"
        self.assertEqual(parse_oom_kill(v2), 1)
        self.assertIsNone(parse_oom_kill("oom_kill_disable 1\n"))

    def test_parse_kmsg_strips_prefix(self) -> None:
        raw = "6,186,424242,-;Out of memory: Killed process 4242 (app)\n"
        self.assertIn("Killed process 4242", parse_kmsg(raw))

    def test_parse_fs_hang(self) -> None:
        text = "nfs: server mn not responding, still trying\n"
        lines = parse_fs_hang(text)
        self.assertEqual(len(lines), 1)
        self.assertIn("mn", lines[0])
        self.assertEqual(parse_fs_hang("all ranks completed\n"), [])

    def test_parse_proc_cgroup_and_find_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = _cgroup_tree(root)
            rels = parse_proc_cgroup("0::/slurm/uid_1000/job_123/step_0\n")
            self.assertEqual(rels, ["/slurm/uid_1000/job_123/step_0"])
            found = find_job_cgroup(
                "123",
                proc_cgroup="0::/slurm/uid_1000/job_123/step_0\n",
                sys_root=root / "sys" / "fs" / "cgroup",
                uid=1000,
            )
            self.assertEqual(found, job)


class TestNodeDiagPluginFixtures(unittest.TestCase):
    def test_plugin_emits_node_local(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = JobContext(job_id="1", host="h1", output_dir=Path(tmp))
            tool = NodeDiag(dmesg_text="Killed process 9 (rank)")
            tool.start(ctx)
            self.assertEqual(tool.events()[0].reason_code, "node_local")
            src = Path(__file__).resolve().parents[1] / "src" / "agent_sidecar" / "tools" / "node_diag.py"
            body = src.read_text(encoding="utf-8")
            self.assertNotIn("workflow_runner", body)
            self.assertNotIn("run-slave", body)

    def test_empty_injection_is_not_anomaly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool = NodeDiag(dmesg_text="")
            tool.start(_ctx(tmp))
            self.assertEqual(tool.events(), [])
            self.assertEqual(anomalies_from_artifacts(Path(tmp)), [])


class TestNodeDiagLiveCollect(unittest.TestCase):
    def test_live_collect_uses_snapshot_and_writes_state(self) -> None:
        seen: list[str] = []

        def collect(ctx: JobContext) -> NodeSnapshot:
            seen.append(ctx.job_id)
            return NodeSnapshot(
                dmesg_text="Out of memory: Killed process 4242 (app)",
                cgroup_procs="4242\n",
                oom_kill=1,
            )

        with tempfile.TemporaryDirectory() as tmp:
            tool = NodeDiag(collect=collect)
            tool.start(_ctx(tmp))
            self.assertEqual(seen, ["123"])
            self.assertEqual(tool.events()[0].reason_code, "node_local")
            snap = (Path(tmp) / "events" / "node-diag.txt").read_text(encoding="utf-8")
            self.assertIn("oom_pids=[4242]", snap)
            self.assertIn("cgroup_pids=[4242]", snap)
            self.assertIn("oom_kill=1", snap)
            self.assertIn("node_local", [a["reason_code"] for a in anomalies_from_artifacts(Path(tmp))])

    def test_stop_refreshes_live_snapshot(self) -> None:
        snaps = [
            NodeSnapshot(dmesg_text="", cgroup_procs="10\n", oom_kill=0),
            NodeSnapshot(
                dmesg_text="Out of memory: Killed process 10 (app)",
                cgroup_procs="10\n",
                oom_kill=1,
            ),
        ]

        def collect(_ctx: JobContext) -> NodeSnapshot:
            return snaps.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            tool = NodeDiag(collect=collect)
            tool.start(_ctx(tmp))
            self.assertEqual(tool.events(), [])
            tool.stop()
            self.assertEqual(tool.events()[0].reason_code, "node_local")
            snap = (Path(tmp) / "events" / "node-diag.txt").read_text(encoding="utf-8")
            self.assertIn("oom_pids=[10]", snap)
            self.assertIn("oom_kill=1", snap)

    def test_injected_fixture_is_not_overwritten_on_stop(self) -> None:
        def collect(_ctx: JobContext) -> NodeSnapshot:
            raise AssertionError("live collect must not run for fixture text")

        with tempfile.TemporaryDirectory() as tmp:
            tool = NodeDiag(dmesg_text="Killed process 9 (rank)", collect=collect)
            tool.start(_ctx(tmp))
            tool.stop()
            self.assertEqual(tool.events()[0].reason_code, "node_local")

    def test_historical_oom_without_cgroup_is_ignored(self) -> None:
        def collect(_ctx: JobContext) -> NodeSnapshot:
            return NodeSnapshot(
                dmesg_text="Out of memory: Killed process 9999 (otherjob)",
                cgroup_procs="",
                oom_kill=0,
            )

        with tempfile.TemporaryDirectory() as tmp:
            tool = NodeDiag(collect=collect)
            tool.start(_ctx(tmp))
            self.assertEqual(tool.events(), [])
            snap = (Path(tmp) / "events" / "node-diag.txt").read_text(encoding="utf-8")
            self.assertIn("oom_pids=[]", snap)

    def test_historical_oom_without_cgroup_match_is_ignored(self) -> None:
        def collect(_ctx: JobContext) -> NodeSnapshot:
            return NodeSnapshot(
                dmesg_text="Out of memory: Killed process 9999 (otherjob)",
                cgroup_procs="10\n11\n",
                oom_kill=0,
            )

        with tempfile.TemporaryDirectory() as tmp:
            tool = NodeDiag(collect=collect)
            tool.start(_ctx(tmp))
            self.assertEqual(tool.events(), [])
            snap = (Path(tmp) / "events" / "node-diag.txt").read_text(encoding="utf-8")
            self.assertIn("oom_pids=[]", snap)
            self.assertEqual(anomalies_from_artifacts(Path(tmp)), [])

    def test_cgroup_oom_kill_delta_emits_node_local(self) -> None:
        snaps = [
            NodeSnapshot(cgroup_procs="10\n", oom_kill=0),
            NodeSnapshot(cgroup_procs="10\n", oom_kill=2),
        ]

        def collect(_ctx: JobContext) -> NodeSnapshot:
            return snaps.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            tool = NodeDiag(collect=collect)
            tool.start(_ctx(tmp))
            self.assertEqual(tool.events(), [])
            tool.stop()
            self.assertEqual(tool.events()[0].reason_code, "node_local")
            snap = (Path(tmp) / "events" / "node-diag.txt").read_text(encoding="utf-8")
            self.assertIn("oom_kill=2", snap)
            self.assertIn("node_local", [a["reason_code"] for a in anomalies_from_artifacts(Path(tmp))])

    def test_fs_hang_emits_node_local(self) -> None:
        def collect(_ctx: JobContext) -> NodeSnapshot:
            return NodeSnapshot(
                dmesg_text="nfs: server mn not responding, still trying",
                fs_hang_lines=("nfs: server mn not responding, still trying",),
            )

        with tempfile.TemporaryDirectory() as tmp:
            tool = NodeDiag(collect=collect)
            tool.start(_ctx(tmp))
            self.assertEqual(tool.events()[0].reason_code, "node_local")
            snap = (Path(tmp) / "events" / "node-diag.txt").read_text(encoding="utf-8")
            self.assertIn("fs_hang_lines=1", snap)
            self.assertIn("node_local", [a["reason_code"] for a in anomalies_from_artifacts(Path(tmp))])

    def test_collect_error_is_fail_soft(self) -> None:
        def collect(_ctx: JobContext) -> NodeSnapshot:
            raise OSError("permission denied")

        with tempfile.TemporaryDirectory() as tmp:
            tool = NodeDiag(collect=collect)
            tool.start(_ctx(tmp))
            self.assertEqual(tool.events(), [])
            err = Path(tmp) / "events" / "node_diag.err"
            self.assertTrue(err.is_file())
            self.assertIn("permission denied", err.read_text(encoding="utf-8"))

    def test_empty_live_snapshot_is_not_anomaly(self) -> None:
        def collect(_ctx: JobContext) -> NodeSnapshot:
            return NodeSnapshot()

        with tempfile.TemporaryDirectory() as tmp:
            tool = NodeDiag(collect=collect)
            tool.start(_ctx(tmp))
            self.assertEqual(tool.events(), [])
            snap = Path(tmp) / "events" / "node-diag.txt"
            self.assertTrue(snap.is_file())
            self.assertIn("oom_pids=[]", snap.read_text(encoding="utf-8"))
            self.assertEqual(anomalies_from_artifacts(Path(tmp)), [])


class TestDefaultNodeCollect(unittest.TestCase):
    def test_reads_kmsg_and_job_cgroup_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _cgroup_tree(root, oom_kill=1, procs="4242\n")
            kmsg = root / "dev" / "kmsg"
            kmsg.parent.mkdir(parents=True)
            kmsg.write_text(
                "6,1,1,-;Out of memory: Killed process 4242 (app)\n",
                encoding="utf-8",
            )
            proc_cgroup = root / "proc" / "self" / "cgroup"
            proc_cgroup.parent.mkdir(parents=True)
            proc_cgroup.write_text("0::/slurm/uid_1000/job_123\n", encoding="utf-8")
            ctx = JobContext(job_id="123", host="h1", output_dir=root)
            snap = default_node_collect(
                ctx,
                dmesg_runner=lambda _argv: "",
                kmsg_path=kmsg,
                proc_cgroup_path=proc_cgroup,
                sys_cgroup_root=root / "sys" / "fs" / "cgroup",
                uid=1000,
            )
            self.assertEqual(parse_oom_trace(snap.dmesg_text), [4242])
            self.assertEqual(parse_cgroup_procs(snap.cgroup_procs), [4242])
            self.assertEqual(snap.oom_kill, 1)
            self.assertTrue(snap.cgroup_path and snap.cgroup_path.endswith("job_123"))

    def test_missing_sources_are_empty_not_raised(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx = JobContext(job_id="123", host="h1", output_dir=root)
            snap = default_node_collect(
                ctx,
                dmesg_runner=lambda _argv: "",
                kmsg_path=root / "missing-kmsg",
                proc_cgroup_path=root / "missing-cgroup",
                sys_cgroup_root=root / "sys" / "fs" / "cgroup",
                uid=1000,
            )
            self.assertEqual(snap.dmesg_text, "")
            self.assertEqual(snap.cgroup_procs, "")
            self.assertIsNone(snap.oom_kill)


class TestClassifyNodeDiag(unittest.TestCase):
    def test_classify_oom_pids_and_oom_kill(self) -> None:
        self.assertEqual(classify_node_diag_text("oom_pids=[4242]\noom_kill=0\n"), "node_local")
        self.assertEqual(classify_node_diag_text("oom_pids=[]\noom_kill=2\n"), "node_local")
        self.assertEqual(classify_node_diag_text("fs_hang_lines=1\n"), "node_local")
        self.assertIsNone(classify_node_diag_text("oom_pids=[]\noom_kill=0\nfs_hang_lines=0\n"))
