"""Copy sidecar + mpi-monitor + eth-monitor trees onto shared NFS."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TextIO

DEFAULT_SHARED = "/shared"

SyncTree = Callable[[Path, Path], None]


class DeployError(Exception):
    """Invalid sidecar, mpi-monitor, or eth-monitor tree."""


@dataclass(frozen=True)
class DeployPlan:
    sidecar_src: Path
    mpi_src: Path
    eth_src: Path
    dest_sidecar: Path
    dest_mpi: Path
    dest_eth: Path
    mpi_pythonpath: Path
    eth_pythonpath: Path
    pythonpath: str
    agent_mpi_monitor_src: str
    agent_eth_monitor_src: str


def default_sidecar_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_shared() -> Path:
    return Path(os.environ.get("AGENT_SHARED") or DEFAULT_SHARED)


def resolve_mpi_pythonpath(mpi_root: Path) -> Path:
    root = mpi_root.resolve()
    if not root.is_dir():
        raise DeployError(f"mpi-monitor tree not found: {root}")
    if (root / "mpi_monitor" / "collect.py").is_file():
        return root
    if (root / "src" / "mpi_monitor" / "collect.py").is_file():
        return root / "src"
    raise DeployError(
        f"not an mpi-monitor tree (need src/mpi_monitor/collect.py): {root}"
    )


def resolve_eth_pythonpath(eth_root: Path) -> Path:
    root = eth_root.resolve()
    if not root.is_dir():
        raise DeployError(f"eth-monitor tree not found: {root}")
    if (root / "eth_monitor" / "collect.py").is_file():
        return root
    if (root / "src" / "eth_monitor" / "collect.py").is_file():
        return root / "src"
    raise DeployError(
        f"not an eth-monitor tree (need src/eth_monitor/collect.py): {root}"
    )


def resolve_sidecar_root(sidecar: Path) -> Path:
    root = sidecar.resolve()
    if (root / "src" / "agent_sidecar").is_dir():
        return root
    raise DeployError(f"not an agent-sidecar tree: {root}")


def _dest_for_src_layout(src: Path, resolved: Path, dest_root: Path) -> tuple[Path, Path]:
    if resolved == src:
        dest = dest_root / "src"
        return dest, dest
    dest = dest_root
    return dest, dest / resolved.relative_to(src)


def plan_deploy(
    sidecar: Path, mpi_monitor: Path, eth_monitor: Path, shared: Path
) -> DeployPlan:
    sidecar_src = resolve_sidecar_root(sidecar)
    mpi_src = mpi_monitor.resolve()
    eth_src = eth_monitor.resolve()
    mpi_resolved = resolve_mpi_pythonpath(mpi_src)
    eth_resolved = resolve_eth_pythonpath(eth_src)
    dest_sidecar = shared / "agent-sidecar"
    dest_mpi, mpi_py = _dest_for_src_layout(mpi_src, mpi_resolved, shared / "mpi-monitor")
    dest_eth, eth_py = _dest_for_src_layout(eth_src, eth_resolved, shared / "eth-monitor")
    pythonpath = f"{dest_sidecar / 'src'}:{mpi_py}:{eth_py}"
    return DeployPlan(
        sidecar_src=sidecar_src,
        mpi_src=mpi_src,
        eth_src=eth_src,
        dest_sidecar=dest_sidecar,
        dest_mpi=dest_mpi,
        dest_eth=dest_eth,
        mpi_pythonpath=mpi_py,
        eth_pythonpath=eth_py,
        pythonpath=pythonpath,
        agent_mpi_monitor_src=str(mpi_py),
        agent_eth_monitor_src=str(eth_py),
    )


def default_sync_tree(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    rsync = shutil.which("rsync")
    if rsync:
        subprocess.check_call(
            [rsync, "-az", "--exclude", ".git", f"{src}/", f"{dest}/"]
        )
        return
    if dest.exists():
        shutil.copytree(
            src, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git")
        )
        return
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))


def format_plan(plan: DeployPlan, *, dry_run: bool) -> str:
    mode = "dry-run" if dry_run else "copy"
    return "\n".join(
        [
            "======== deploy ========",
            f"mode    : {mode}",
            f"sidecar : {plan.sidecar_src}  ->  {plan.dest_sidecar}",
            f"mpi-mon : {plan.mpi_src}  ->  {plan.dest_mpi}",
            f"eth-mon : {plan.eth_src}  ->  {plan.dest_eth}",
            f"AGENT_MPI_MONITOR_SRC={plan.agent_mpi_monitor_src}",
            f"AGENT_ETH_MONITOR_SRC={plan.agent_eth_monitor_src}",
            f"PYTHONPATH={plan.pythonpath}",
            f"wrap    : {plan.dest_sidecar}/scripts/sidecar.sh srun ...",
            f"analy   : {plan.dest_sidecar}/scripts/sidecar-analy.sh --log <run_dir> --code /path/to/src",
            "",
        ]
    )


def _import_check(plan: DeployPlan, stdout: TextIO) -> int:
    env = {**os.environ, "PYTHONPATH": plan.pythonpath}
    script = (
        "import agent_sidecar\n"
        "from mpi_monitor.collect import collect_loop as mpi_loop\n"
        "from eth_monitor.collect import collect_loop as eth_loop\n"
        "import mpi_monitor, eth_monitor\n"
        "print('agent_sidecar', getattr(agent_sidecar, '__version__', '?'))\n"
        "print('mpi_monitor ', mpi_monitor.__file__)\n"
        "print('eth_monitor ', eth_monitor.__file__)\n"
        "print('mpi_loop', mpi_loop)\n"
        "print('eth_loop', eth_loop)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
    )
    stdout.write("======== import check ========\n")
    if proc.stdout:
        stdout.write(proc.stdout)
        if not proc.stdout.endswith("\n"):
            stdout.write("\n")
    if proc.returncode != 0:
        stdout.write(proc.stderr or "import failed\n")
        return 1
    stdout.write(
        "\nagent srun injects PYTHONPATH as "
        "{sidecar}/src:{AGENT_MPI_MONITOR_SRC:-/shared/mpi-monitor/src}"
        ":{AGENT_ETH_MONITOR_SRC:-/shared/eth-monitor/src}\n"
        f"{plan.dest_sidecar}/scripts/sidecar.sh srun ...\n"
        f"{plan.dest_sidecar}/scripts/sidecar-analy.sh --log <run_dir> "
        "--code /path/to/src\n"
    )
    return 0


def run_deploy(
    sidecar: Path,
    mpi_monitor: Path,
    eth_monitor: Path,
    shared: Path,
    *,
    dry_run: bool = False,
    sync_tree: SyncTree | None = None,
    stdout: TextIO | None = None,
) -> int:
    out = stdout or sys.stdout
    try:
        plan = plan_deploy(sidecar, mpi_monitor, eth_monitor, shared)
    except DeployError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    out.write(format_plan(plan, dry_run=dry_run))
    if dry_run:
        out.write("dry-run: no files copied\n")
        return 0
    sync = sync_tree or default_sync_tree
    shared.mkdir(parents=True, exist_ok=True)
    sync(plan.sidecar_src, plan.dest_sidecar)
    sync(plan.mpi_src, plan.dest_mpi)
    sync(plan.eth_src, plan.dest_eth)
    return _import_check(plan, out)
