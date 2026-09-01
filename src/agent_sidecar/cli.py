"""agent CLI: srun / sbatch / salloc / supervisor / report."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from agent_sidecar.argv import AgentParseError, apply_profile_defaults, parse_agent_argv
from agent_sidecar.run import sbatch_environ, submit_sbatch, wrap_srun
from agent_sidecar.spi import JobContext, start_supervisor
from agent_sidecar.telemetry import load_telemetry
from agent_sidecar.tools.mpi_scan import MpiScan
from agent_sidecar.tools.node_diag import NodeDiag
from agent_sidecar.tools.proc_monitor import ProcMonitor
from agent_sidecar.tools.slurm_tap import SlurmTap

USAGE = "usage: agent srun|sbatch|salloc|supervisor|report ..."

PLUGIN_FACTORIES = {
    "proc-monitor": ProcMonitor,
    "mpi-scan": MpiScan,
    "slurm-tap": SlurmTap,
    "node-diag": NodeDiag,
}


def _spawn(argv: list[str]) -> int:
    return subprocess.call(argv)


def _plugins_for(skills: tuple[str, ...]) -> list:
    names = skills or ("proc-monitor",)
    plugins = []
    for name in names:
        factory = PLUGIN_FACTORIES.get(name)
        if factory is None:
            raise AgentParseError(f"unknown skill: {name}")
        plugins.append(factory())
    return plugins


def cmd_srun(parsed, *, run_sidecar=None, run_user=None, overlap_ok: bool = True) -> int:
    code, _run_dir, _plan = wrap_srun(
        parsed,
        env=dict(os.environ),
        run_sidecar=run_sidecar or _spawn,
        run_user=run_user or _spawn,
        overlap_ok=overlap_ok,
    )
    return code


def cmd_sbatch(parsed) -> int:
    script = None
    extra: list[str] = []
    for tok in parsed.passthrough:
        if tok.endswith(".sh") or Path(tok).suffix in {".sh", ".bash", ".slurm"}:
            script = Path(tok)
        else:
            extra.append(tok)
    if script is None and parsed.passthrough:
        script = Path(parsed.passthrough[-1])
        extra = parsed.passthrough[:-1]
    if script is None:
        raise AgentParseError("sbatch requires a script path")

    def runner(argv: list[str], env: dict[str, str]) -> int:
        merged = {**os.environ, **env}
        return subprocess.call(argv, env=merged)

    return submit_sbatch(script, parsed.options, runner=runner, extra_sbatch=extra)


def cmd_salloc(parsed) -> int:
    env = {**os.environ, **sbatch_environ(parsed.options)}
    return subprocess.call(["salloc", *parsed.passthrough], env=env)


def cmd_exec_wrap(command: list[str]) -> int:
    """Fork a placeholder child, then exec the user binary (PMI pid = app)."""
    import os

    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("exec-wrap requires a command", file=sys.stderr)
        return 2
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.execvp(command[0], command)
    return 127


def cmd_supervisor(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="agent supervisor")
    p.add_argument("--job-id", required=True)
    p.add_argument("--host", default=os.uname().nodename.split(".")[0])
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--skills", default="proc-monitor")
    ns = p.parse_args(argv)
    skills = tuple(s for s in ns.skills.split(",") if s)
    ctx = JobContext(job_id=ns.job_id, host=ns.host, output_dir=ns.output_dir)
    start_supervisor(ns.job_id, ns.host, _plugins_for(skills), ctx)
    return 0


def cmd_report(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="agent report")
    p.add_argument("--run-dir", required=True, type=Path)
    ns = p.parse_args(argv)
    doc = load_telemetry(ns.run_dir)
    print(json.dumps(doc, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    cmd = argv[0]
    if cmd in {"-h", "--help"}:
        print(USAGE)
        return 0
    try:
        if cmd == "supervisor":
            return cmd_supervisor(argv[1:])
        if cmd == "report":
            return cmd_report(argv[1:])
        parsed = parse_agent_argv(argv)
        apply_profile_defaults(parsed.options)
        if parsed.options.node_llm:
            print("--agent-node-llm is unsupported in phase 1", file=sys.stderr)
        if parsed.command == "srun":
            return cmd_srun(parsed)
        if parsed.command == "sbatch":
            return cmd_sbatch(parsed)
        if parsed.command == "salloc":
            return cmd_salloc(parsed)
        if parsed.command == "exec-wrap":
            return cmd_exec_wrap(parsed.passthrough)
        raise AgentParseError(f"unknown command: {parsed.command}")
    except AgentParseError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
