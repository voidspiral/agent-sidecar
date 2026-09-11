"""agent CLI: srun / sbatch / salloc / supervisor / report / serve / analy."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from agent_sidecar.argv import (
    DEFAULT_SKILLS,
    AgentParseError,
    agent_quiet,
    apply_profile_defaults,
    parse_agent_argv,
)
from agent_sidecar.report import format_run_report, write_run_report
from agent_sidecar.run import (
    agent_stop_path,
    request_agent_stop,
    run_user_command,
    sbatch_environ,
    submit_sbatch,
    wrap_srun,
)
from agent_sidecar.spi import JobContext, start_supervisor
from agent_sidecar.telemetry import load_telemetry
from agent_sidecar.tools.mpi_scan import MpiScan
from agent_sidecar.tools.node_diag import NodeDiag
from agent_sidecar.tools.proc_monitor import ProcMonitor
from agent_sidecar.tools.slurm_tap import SlurmTap

USAGE = "usage: agent srun|sbatch|salloc|supervisor|report|serve|analy ..."

PLUGIN_FACTORIES = {
    "proc-monitor": ProcMonitor,
    "mpi-scan": MpiScan,
    "slurm-tap": SlurmTap,
    "node-diag": NodeDiag,
}


def reap_sidecar(proc: subprocess.Popen, *, timeout: float = 15.0) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _log(msg: str) -> None:
    print(f"[agent] {msg}", flush=True)


def _spawn(argv: list[str]) -> int:
    return subprocess.call(argv)


def cmd_srun(
    parsed,
    *,
    run_sidecar=None,
    run_user=None,
    overlap_ok: bool = True,
    opencode_runner=None,
    live_watcher=None,
    live_plotter=None,
    tty: bool | None = None,
) -> int:
    verbose = parsed.options.verbose or os.environ.get("AGENT_VERBOSE") == "1"
    quiet = agent_quiet(parsed.options)
    if quiet:
        verbose = False
    holder: dict[str, subprocess.Popen[str]] = {}

    def default_sidecar(argv: list[str]) -> int:
        if verbose:
            _log("start sidecar step: " + " ".join(argv))
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.DEVNULL if quiet else None,
            stderr=subprocess.DEVNULL if quiet else None,
        )
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            rc = proc.poll()
            if rc is not None:
                if verbose:
                    _log(f"sidecar step exited immediately rc={rc}")
                return rc
            time.sleep(0.2)
        holder["proc"] = proc
        if verbose:
            _log(f"sidecar is running (pid={proc.pid})")
        return 0

    def default_user(argv: list[str]) -> int:
        if verbose:
            _log("start user step: " + " ".join(argv))
        return run_user_command(argv)

    if verbose:
        _log(f"profile={parsed.options.profile} skills={parsed.options.skills or DEFAULT_SKILLS}")
        _log("passthrough=" + " ".join(parsed.passthrough))
    if quiet:
        _log("sidecar started")
        _log("user step started")

    code, run_dir, plan = wrap_srun(
        parsed,
        env=dict(os.environ),
        run_sidecar=run_sidecar or default_sidecar,
        run_user=run_user or default_user,
        overlap_ok=overlap_ok,
        opencode_runner=opencode_runner,
        live_watcher=live_watcher,
        live_plotter=live_plotter,
        tty=tty,
    )
    proc = holder.get("proc")
    if proc is not None:
        request_agent_stop(run_dir)
        if verbose:
            _log(f"stop sidecar (pid={proc.pid})")
        reap_sidecar(proc)
    if quiet:
        _log(f"user exit={code}")
        write_run_report(run_dir)
        print(format_run_report(run_dir), end="", flush=True)
    elif verbose:
        _log(f"mode={plan.mode} fallback={plan.fallback_used} user_exit={code}")
        _log(f"run_dir={run_dir}")
        tel = run_dir / "telemetry.json"
        if tel.is_file():
            _log("telemetry.json:")
            print(tel.read_text(encoding="utf-8"), flush=True)
    return code


def _plugins_for(skills: tuple[str, ...]) -> list:
    names = skills or DEFAULT_SKILLS
    plugins = []
    for name in names:
        factory = PLUGIN_FACTORIES.get(name)
        if factory is None:
            raise AgentParseError(f"unknown skill: {name}")
        plugins.append(factory())
    return plugins


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
    p.add_argument("--skills", default=",".join(DEFAULT_SKILLS))
    p.add_argument("--match", default="")
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--once", action="store_true", help="start plugins and exit (tests)")
    ns = p.parse_args(argv)
    skills = tuple(s for s in ns.skills.split(",") if s)
    ctx = JobContext(
        job_id=ns.job_id,
        host=ns.host,
        output_dir=ns.output_dir,
        match=ns.match or None,
        interval=ns.interval,
    )
    if os.environ.get("AGENT_QUIET") != "1":
        print(
            f"[sidecar] host={ns.host} job={ns.job_id} pid={os.getpid()} skills={','.join(skills)}",
            flush=True,
        )
    sup = start_supervisor(ns.job_id, ns.host, _plugins_for(skills), ctx)
    if ns.once:
        sup.stop()
        return 0
    stop = {"n": False}

    def _handle(signum: int, _frame: object) -> None:
        if os.environ.get("AGENT_QUIET") != "1":
            print(f"[sidecar] host={ns.host} got signal {signum}, stopping", flush=True)
        stop["n"] = True

    try:
        signal.signal(signal.SIGTERM, _handle)
        signal.signal(signal.SIGINT, _handle)
    except ValueError:
        pass
    stop_path = agent_stop_path(ns.output_dir)
    while not stop["n"]:
        if stop_path.is_file():
            break
        time.sleep(0.2)
    sup.stop()
    if os.environ.get("AGENT_QUIET") != "1":
        print(f"[sidecar] host={ns.host} stopped", flush=True)
    return 0


def cmd_report(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="agent report")
    p.add_argument("--run-dir", required=True, type=Path)
    ns = p.parse_args(argv)
    doc = load_telemetry(ns.run_dir)
    print(json.dumps(doc, indent=2))
    return 0


def cmd_analy(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="agent analy")
    p.add_argument("--run-dir", required=True, type=Path)
    p.add_argument("--code", type=Path, default=None, help="optional read-only source tree")
    p.add_argument("--llm", action="store_true", help="opt-in OpenCode after deterministic pack")
    try:
        ns = p.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    if not ns.run_dir.is_dir():
        print(f"run-dir not found: {ns.run_dir}", file=sys.stderr)
        return 2
    from agent_sidecar.analysis import run_analysis
    from agent_sidecar.opencode_assist import default_opencode_runner

    print(
        f"[agent] analy run_dir={ns.run_dir}"
        + (f" code={ns.code}" if ns.code else "")
        + (" llm=1" if ns.llm else " llm=0"),
        flush=True,
    )
    if ns.llm:
        print("[agent] analy: deterministic pack then OpenCode (may take up to AGENT_OPENCODE_TIMEOUT)", flush=True)
    result = run_analysis(
        ns.run_dir,
        code_root=ns.code,
        use_llm=bool(ns.llm),
        opencode_runner=default_opencode_runner if ns.llm else None,
        env=dict(os.environ),
    )
    analysis_path = ns.run_dir / "assist" / "analysis.json"
    job_path = ns.run_dir / "assist" / "job.json"
    print(f"[agent] analy pack={result.get('pack')} -> {analysis_path}", flush=True)
    if job_path.is_file():
        print(f"[agent] analy job-assist -> {job_path}", flush=True)
        try:
            note = json.loads(job_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[agent] analy: cannot read job.json: {exc}", file=sys.stderr, flush=True)
            return 0
        reason = note.get("suspected_reason") or result.get("reason_code") or ""
        summary = str(note.get("summary") or "").strip()
        print(f"[agent] suspected_reason={reason}", flush=True)
        if summary:
            print("[agent] summary:", flush=True)
            print(summary, flush=True)
        else:
            print("[agent] summary: (empty)", file=sys.stderr, flush=True)
    elif ns.llm:
        print("[agent] analy: OpenCode did not write assist/job.json", file=sys.stderr, flush=True)
    return 0


def cmd_serve(argv: list[str]) -> int:
    from agent_sidecar.live_plot_http import DEFAULT_HOST, DEFAULT_PORT, LivePlotServer

    p = argparse.ArgumentParser(prog="agent serve")
    p.add_argument("--run-dir", required=True, type=Path)
    p.add_argument("--host", default=os.environ.get("AGENT_LIVE_PLOT_HOST") or DEFAULT_HOST)
    raw_port = os.environ.get("AGENT_LIVE_PLOT_PORT") or str(DEFAULT_PORT)
    try:
        default_port = int(raw_port)
    except ValueError:
        default_port = DEFAULT_PORT
    p.add_argument("--port", type=int, default=default_port)
    ns = p.parse_args(argv)
    server = LivePlotServer(host=ns.host, port=ns.port)
    url = server.start(ns.run_dir)
    print(f"[agent] live plot: {url}", flush=True)
    try:
        server.wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
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
        if cmd == "analy":
            return cmd_analy(argv[1:])
        if cmd == "serve":
            return cmd_serve(argv[1:])
        parsed = parse_agent_argv(argv)
        apply_profile_defaults(parsed.options)
        if parsed.options.node_llm:
            print("--agent-node-llm is unsupported", file=sys.stderr)
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
