"""NFS deploy planner: sidecar + mpi-monitor trees."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_sidecar.cli import main
from agent_sidecar.deploy import (
    DeployError,
    plan_deploy,
    resolve_mpi_pythonpath,
    run_deploy,
)


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sidecar_tree(root: Path) -> Path:
    _write(root / "src" / "agent_sidecar" / "__init__.py", '__version__ = "0.1.0"\n')
    return root


def _mpi_tree(root: Path) -> Path:
    _write(
        root / "src" / "mpi_monitor" / "collect.py",
        "def collect_loop(**kwargs):\n    return None\n",
    )
    _write(root / "src" / "mpi_monitor" / "__init__.py", "")
    return root


class TestResolveMpiPythonpath(unittest.TestCase):
    def test_repo_layout_uses_src(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = _mpi_tree(Path(tmp) / "mpi-monitor")
            self.assertEqual(resolve_mpi_pythonpath(tree), tree / "src")

    def test_src_dir_itself_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = _mpi_tree(Path(tmp) / "mpi-monitor")
            src = tree / "src"
            self.assertEqual(resolve_mpi_pythonpath(src), src)

    def test_rejects_unrelated_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            junk = Path(tmp) / "not-mpi"
            junk.mkdir()
            with self.assertRaises(DeployError) as ctx:
                resolve_mpi_pythonpath(junk)
            self.assertIn("mpi-monitor", str(ctx.exception))


class TestPlanDeploy(unittest.TestCase):
    def test_maps_trees_onto_shared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sidecar = _sidecar_tree(base / "agent-sidecar")
            mpi = _mpi_tree(base / "mpi-monitor")
            shared = base / "shared"
            plan = plan_deploy(sidecar, mpi, shared)
            self.assertEqual(plan.dest_sidecar, shared / "agent-sidecar")
            self.assertEqual(plan.dest_mpi, shared / "mpi-monitor")
            self.assertEqual(plan.mpi_pythonpath, shared / "mpi-monitor" / "src")
            self.assertEqual(plan.agent_mpi_monitor_src, str(shared / "mpi-monitor" / "src"))
            self.assertIn(str(shared / "agent-sidecar" / "src"), plan.pythonpath)
            self.assertIn(str(shared / "mpi-monitor" / "src"), plan.pythonpath)

    def test_src_dir_lands_under_shared_mpi_monitor_src(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sidecar = _sidecar_tree(base / "agent-sidecar")
            mpi_src = _mpi_tree(base / "mpi-monitor") / "src"
            plan = plan_deploy(sidecar, mpi_src, base / "shared")
            self.assertEqual(plan.dest_mpi, base / "shared" / "mpi-monitor" / "src")
            self.assertEqual(plan.mpi_pythonpath, base / "shared" / "mpi-monitor" / "src")
            self.assertEqual(
                plan.agent_mpi_monitor_src,
                str(base / "shared" / "mpi-monitor" / "src"),
            )

    def test_rejects_non_sidecar_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            mpi = _mpi_tree(base / "mpi-monitor")
            with self.assertRaises(DeployError) as ctx:
                plan_deploy(base / "missing", mpi, base / "shared")
            self.assertIn("agent-sidecar", str(ctx.exception))


class TestRunDeploy(unittest.TestCase):
    def test_dry_run_does_not_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sidecar = _sidecar_tree(base / "agent-sidecar")
            mpi = _mpi_tree(base / "mpi-monitor")
            shared = base / "shared"
            buf = io.StringIO()
            copies: list[tuple[str, str]] = []

            def sync(src: Path, dest: Path) -> None:
                copies.append((str(src), str(dest)))

            code = run_deploy(
                sidecar,
                mpi,
                shared,
                dry_run=True,
                sync_tree=sync,
                stdout=buf,
            )
            self.assertEqual(code, 0)
            self.assertEqual(copies, [])
            text = buf.getvalue()
            self.assertIn("mpi-monitor", text)
            self.assertIn(str(mpi), text)
            self.assertIn(str(shared / "mpi-monitor"), text)
            self.assertIn("AGENT_MPI_MONITOR_SRC=", text)
            self.assertIn("/mpi-monitor/src", text)

    def test_copies_both_trees_and_prints_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sidecar = _sidecar_tree(base / "agent-sidecar")
            mpi = _mpi_tree(base / "mpi-monitor")
            shared = base / "shared"
            buf = io.StringIO()
            code = run_deploy(sidecar, mpi, shared, dry_run=False, stdout=buf)
            self.assertEqual(code, 0)
            self.assertTrue((shared / "agent-sidecar" / "src" / "agent_sidecar" / "__init__.py").is_file())
            self.assertTrue((shared / "mpi-monitor" / "src" / "mpi_monitor" / "collect.py").is_file())
            text = buf.getvalue()
            self.assertIn(f"AGENT_MPI_MONITOR_SRC={shared / 'mpi-monitor' / 'src'}", text)
            self.assertIn("PYTHONPATH=", text)


class TestDeployCli(unittest.TestCase):
    def test_requires_mpi_monitor(self) -> None:
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf):
            code = main(["deploy"])
        self.assertEqual(code, 2)
        self.assertIn("mpi-monitor", buf.getvalue())

    def test_dry_run_cli_prints_mpi_monitor_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sidecar = _sidecar_tree(base / "agent-sidecar")
            mpi = _mpi_tree(base / "mpi-monitor")
            shared = base / "shared"
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = main(
                    [
                        "deploy",
                        "--sidecar",
                        str(sidecar),
                        "--mpi-monitor",
                        str(mpi),
                        "--shared",
                        str(shared),
                        "--dry-run",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertFalse(shared.exists())
            self.assertIn(str(mpi), buf.getvalue())
            self.assertIn("AGENT_MPI_MONITOR_SRC=", buf.getvalue())

    def test_positional_mpi_monitor_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sidecar = _sidecar_tree(base / "agent-sidecar")
            mpi = _mpi_tree(base / "mpi-monitor")
            shared = base / "shared"
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = main(
                    [
                        "deploy",
                        "--sidecar",
                        str(sidecar),
                        "--shared",
                        str(shared),
                        "--dry-run",
                        str(mpi),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn(str(mpi), buf.getvalue())
