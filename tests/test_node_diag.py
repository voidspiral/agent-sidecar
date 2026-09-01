"""node-diag tests (OOM / cgroup fixtures)."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from agent_sidecar.spi import JobContext
from agent_sidecar.tools.node_diag import NodeDiag, parse_cgroup_procs, parse_oom_trace


class TestNodeDiag(unittest.TestCase):
    def test_oom_and_cgroup_parse(self) -> None:
        dmesg = "Out of memory: Killed process 4242 (app) total-vm:100000kB"
        self.assertEqual(parse_oom_trace(dmesg), [4242])
        self.assertEqual(parse_cgroup_procs("10\n11\n"), [10, 11])

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
