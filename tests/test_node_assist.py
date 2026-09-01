"""Node-assist notes; never scancel/scontrol."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import tempfile
import unittest
from pathlib import Path

from agent_sidecar.assist import note_invokes_slurm, write_node_assist_note
from agent_sidecar.spi import Event


class TestNodeAssist(unittest.TestCase):
    def test_writes_note_under_assist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            evidence = run_dir / "events" / "x.txt"
            evidence.parent.mkdir(parents=True)
            evidence.write_text("x", encoding="utf-8")
            path = write_node_assist_note(
                run_dir,
                host="h1",
                events=[Event(reason_code="mpi_abort", message="abort")],
                artifacts=[evidence],
            )
            self.assertEqual(path.parent.name, "assist")
            note = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(note["host"], "h1")
            self.assertEqual(note["suspected_reason"], "mpi_abort")
            self.assertFalse(note_invokes_slurm(note))
            self.assertEqual(note["actions"], [])
            blob = path.read_text(encoding="utf-8")
            self.assertNotIn("scancel", blob)
            # scontrol must not appear as an action; the word may appear in docs only
            self.assertNotIn('"scontrol"', blob)
