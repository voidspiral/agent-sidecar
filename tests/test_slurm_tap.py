"""slurm-tap tests on fixture text."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from agent_sidecar.spi import JobContext
from agent_sidecar.tools.slurm_tap import SlurmTap, parse_sacct, parse_scontrol


SCONTROL = """
JobId=123 JobName=app UserId=u(1000) JobState=OUT_OF_MEMORY NodeList=h1,h2 ExitCode=0:0
"""

SACCT = """
JobID|State|ExitCode|MaxRSS
123|NODE_FAIL|1:0|100K
"""


class TestSlurmTap(unittest.TestCase):
    def test_parse_scontrol_oom(self) -> None:
        rec = parse_scontrol(SCONTROL)
        self.assertEqual(rec["JobId"], "123")
        self.assertEqual(rec["JobState"], "OUT_OF_MEMORY")
        self.assertEqual(rec["NodeList"], "h1,h2")

    def test_parse_sacct_node_fail(self) -> None:
        rec = parse_sacct(SACCT)
        self.assertEqual(rec["State"], "NODE_FAIL")

    def test_plugin_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = JobContext(job_id="123", host="h1", output_dir=Path(tmp))
            tool = SlurmTap(scontrol_text=SCONTROL)
            tool.start(ctx)
            self.assertEqual(tool.events()[0].reason_code, "slurm_oom")
