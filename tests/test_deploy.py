"""NFS deploy planner: sidecar + mpi-monitor + eth-monitor trees."""

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
    resolve_eth_pythonpath,
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


def _eth_tree(root: Path) -> Path:
    _write(
        root / "src" / "eth_monitor" / "collect.py",
        "def collect_loop(**kwargs):\n    return None\n",
    )
    _write(root / "src" / "eth_monitor" / "__init__.py", "")
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


class TestResolveEthPythonpath(unittest.TestCase):
    def test_repo_layout_uses_src(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = _eth_tree(Path(tmp) / "eth-monitor")
            self.assertEqual(resolve_eth_pythonpath(tree), tree / "src")


class TestPlanDeploy(unittest.TestCase):
    def test_maps_trees_onto_shared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sidecar = _sidecar_tree(base / "agent-sidecar")
            mpi = _mpi_tree(base / "mpi-monitor")
            eth = _eth_tree(base / "eth-monitor")
            shared = base / "shared"
            plan = plan_deploy(sidecar, mpi, eth, shared)
            self.assertEqual(plan.dest_sidecar, shared / "agent-sidecar")
            self.assertEqual(plan.dest_mpi, shared / "mpi-monitor")
            self.assertEqual(plan.dest_eth, shared / "eth-monitor")
            self.assertEqual(plan.mpi_pythonpath, shared / "mpi-monitor" / "src")
            self.assertEqual(plan.eth_pythonpath, shared / "eth-monitor" / "src")
            self.assertEqual(plan.agent_mpi_monitor_src, str(shared / "mpi-monitor" / "src"))
            self.assertEqual(plan.agent_eth_monitor_src, str(shared / "eth-monitor" / "src"))
            self.assertIn(str(shared / "agent-sidecar" / "src"), plan.pythonpath)
            self.assertIn(str(shared / "mpi-monitor" / "src"), plan.pythonpath)
            self.assertIn(str(shared / "eth-monitor" / "src"), plan.pythonpath)

    def test_src_dir_lands_under_shared_mpi_monitor_src(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sidecar = _sidecar_tree(base / "agent-sidecar")
            mpi_src = _mpi_tree(base / "mpi-monitor") / "src"
            eth = _eth_tree(base / "eth-monitor")
            plan = plan_deploy(sidecar, mpi_src, eth, base / "shared")
            self.assertEqual(plan.dest_mpi, base / "shared" / "mpi-monitor" / "src")
            self.assertEqual(plan.mpi_pythonpath, base / "shared" / "mpi-monitor" / "src")

    def test_rejects_non_sidecar_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            mpi = _mpi_tree(base / "mpi-monitor")
            eth = _eth_tree(base / "eth-monitor")
            with self.assertRaises(DeployError) as ctx:
                plan_deploy(base / "missing", mpi, eth, base / "shared")
            self.assertIn("agent-sidecar", str(ctx.exception))


class TestRunDeploy(unittest.TestCase):
    def test_dry_run_does_not_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sidecar = _sidecar_tree(base / "agent-sidecar")
            mpi = _mpi_tree(base / "mpi-monitor")
            eth = _eth_tree(base / "eth-monitor")
            shared = base / "shared"
            buf = io.StringIO()
            copies: list[tuple[str, str]] = []

            def sync(src: Path, dest: Path) -> None:
                copies.append((str(src), str(dest)))

            code = run_deploy(
                sidecar,
                mpi,
                eth,
                shared,
                dry_run=True,
                sync_tree=sync,
                stdout=buf,
            )
            self.assertEqual(code, 0)
            self.assertEqual(copies, [])
            text = buf.getvalue()
            self.assertIn("mpi-monitor", text)
            self.assertIn("eth-monitor", text)
            self.assertIn(str(mpi), text)
            self.assertIn("AGENT_MPI_MONITOR_SRC=", text)
            self.assertIn("AGENT_ETH_MONITOR_SRC=", text)
            self.assertIn("scripts/sidecar.sh", text)

    def test_copies_three_trees_and_prints_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sidecar = _sidecar_tree(base / "agent-sidecar")
            mpi = _mpi_tree(base / "mpi-monitor")
            eth = _eth_tree(base / "eth-monitor")
            shared = base / "shared"
            buf = io.StringIO()
            code = run_deploy(sidecar, mpi, eth, shared, dry_run=False, stdout=buf)
            self.assertEqual(code, 0)
            self.assertTrue((shared / "agent-sidecar" / "src" / "agent_sidecar" / "__init__.py").is_file())
            self.assertTrue((shared / "mpi-monitor" / "src" / "mpi_monitor" / "collect.py").is_file())
            self.assertTrue((shared / "eth-monitor" / "src" / "eth_monitor" / "collect.py").is_file())
            text = buf.getvalue()
            self.assertIn(f"AGENT_MPI_MONITOR_SRC={shared / 'mpi-monitor' / 'src'}", text)
            self.assertIn(f"AGENT_ETH_MONITOR_SRC={shared / 'eth-monitor' / 'src'}", text)
            self.assertIn("PYTHONPATH=", text)


class TestDeployCli(unittest.TestCase):
    def test_requires_both_trees(self) -> None:
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf):
            code = main(["deploy"])
        self.assertEqual(code, 2)
        self.assertIn("eth-monitor", buf.getvalue())

    def test_dry_run_cli_prints_both_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sidecar = _sidecar_tree(base / "agent-sidecar")
            mpi = _mpi_tree(base / "mpi-monitor")
            eth = _eth_tree(base / "eth-monitor")
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
                        "--eth-monitor",
                        str(eth),
                        "--shared",
                        str(shared),
                        "--dry-run",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertFalse(shared.exists())
            self.assertIn(str(mpi), buf.getvalue())
            self.assertIn(str(eth), buf.getvalue())
            self.assertIn("AGENT_ETH_MONITOR_SRC=", buf.getvalue())

    def test_positional_mpi_then_eth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sidecar = _sidecar_tree(base / "agent-sidecar")
            mpi = _mpi_tree(base / "mpi-monitor")
            eth = _eth_tree(base / "eth-monitor")
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
                        str(eth),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn(str(mpi), buf.getvalue())
            self.assertIn(str(eth), buf.getvalue())


class TestSidecarPythonpath(unittest.TestCase):
    def test_three_entries_with_env_overrides(self) -> None:
        from agent_sidecar.run import sidecar_pythonpath

        path = sidecar_pythonpath(
            "/shared/agent-sidecar/src",
            {
                "AGENT_MPI_MONITOR_SRC": "/shared/mpi-monitor/src",
                "AGENT_ETH_MONITOR_SRC": "/shared/eth-monitor/src",
            },
        )
        self.assertEqual(
            path,
            "/shared/agent-sidecar/src:/shared/mpi-monitor/src:/shared/eth-monitor/src",
        )

    def test_defaults_include_eth_monitor(self) -> None:
        from agent_sidecar.run import sidecar_pythonpath

        path = sidecar_pythonpath("/opt/sidecar/src", {})
        self.assertEqual(
            path,
            "/opt/sidecar/src:/shared/mpi-monitor/src:/shared/eth-monitor/src",
        )
