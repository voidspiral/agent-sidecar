"""Run a wrapped srun and preserve the user exit code."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_sidecar.argv import AgentOptions, ParsedArgv, agent_quiet, apply_profile_defaults
from agent_sidecar.assist import run_job_assist
from agent_sidecar.launch import LaunchPlan, execute_launch, plan_overlap
from agent_sidecar.live_opencode import ATTACH_HINT, LiveWatcher
from agent_sidecar.telemetry import (
    anomalies_from_artifacts,
    ensure_run_layout,
    make_run_id,
    retry_metadata,
    rollup_reason_code,
    summarize_series,
    write_meta,
    write_telemetry,
)
from agent_sidecar.tools.plot import plot_run

Runner = Callable[[list[str]], int]

_LLM_ENV_KEYS = (
    "AGENT_LLM_API_KEY",
    "AGENT_LLM_BASE_URL",
    "AGENT_LLM_MODEL",
    "AGENT_LLM_TIMEOUT",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_MODEL",
)

DEFAULT_MPI_MONITOR_SRC = "/shared/mpi-monitor/src"
DEFAULT_JOB_DIR_SHARED = "/shared/agent-runs"
AGENT_STOP_NAME = ".agent-stop"
LAUNCHERS = {
    "srun",
    "mpirun",
    "mpiexec",
    "orted",
    "orterun",
    "prted",
    "prterun",
}


def resolve_output_dir(options: AgentOptions, env: dict[str, str]) -> Path:
    raw = options.output_dir or env.get("AGENT_JOB_DIR")
    if not raw:
        raw = DEFAULT_JOB_DIR_SHARED if Path("/shared").is_dir() else "runs"
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def sidecar_pythonpath(src_dir: str, env: dict[str, str]) -> str:
    mpi = env.get("AGENT_MPI_MONITOR_SRC") or DEFAULT_MPI_MONITOR_SRC
    return f"{src_dir}:{mpi}"


def agent_stop_path(run_dir: Path) -> Path:
    return Path(run_dir) / AGENT_STOP_NAME


def request_agent_stop(run_dir: Path) -> Path:
    path = agent_stop_path(run_dir)
    path.write_text("stop\n", encoding="utf-8")
    return path


def user_command_match(passthrough: list[str], override: str | None) -> str:
    if override:
        return override
    args = list(passthrough)
    if "--" in args:
        cmd = args[args.index("--") + 1 :]
    else:
        cmd = [t for t in args if not t.startswith("-")]
    if not cmd:
        return ""
    name = Path(cmd[0]).name
    if name in LAUNCHERS:
        return ""
    return name


def merge_event_errors(run_dir: Path, errors: dict[str, str]) -> dict[str, str]:
    events_dir = run_dir / "events"
    if not events_dir.is_dir():
        return errors
    for path in events_dir.glob("*.err"):
        errors[path.stem] = path.read_text(encoding="utf-8", errors="replace")[:500]
    return errors


def wrap_srun(
    parsed: ParsedArgv,
    *,
    env: dict[str, str],
    run_sidecar: Runner,
    run_user: Runner,
    overlap_ok: bool = True,
    collect_errors: dict[str, str] | None = None,
    plotter=None,
    opencode_runner=None,
    live_watcher=None,
    tty: bool | None = None,
) -> tuple[int, Path, LaunchPlan]:
    apply_profile_defaults(parsed.options)
    quiet = agent_quiet(parsed.options, env)
    prev_quiet = os.environ.get("AGENT_QUIET")
    quiet_injected = False
    if quiet:
        env["AGENT_QUIET"] = "1"
        if prev_quiet != "1":
            os.environ["AGENT_QUIET"] = "1"
            quiet_injected = True
    out_root = resolve_output_dir(parsed.options, env)
    run_dir = out_root / make_run_id(pid=0)
    ensure_run_layout(run_dir)
    src_dir = str(Path(__file__).resolve().parents[1])
    exe = sys.executable
    py_path = sidecar_pythonpath(src_dir, env)
    unset_flags: list[str] = []
    for key in _LLM_ENV_KEYS:
        unset_flags.extend(["-u", key])
    py_mod = [
        "env",
        *unset_flags,
        f"PYTHONPATH={py_path}",
        "PYTHONUNBUFFERED=1",
        exe,
        "-m",
        "agent_sidecar",
    ]
    match = user_command_match(parsed.passthrough, parsed.options.match)
    supervisor = [
        *py_mod,
        "supervisor",
        "--job-id",
        env.get("SLURM_JOB_ID", "0"),
        "--output-dir",
        str(run_dir),
        "--skills",
        ",".join(parsed.options.skills) or "proc-monitor",
        "--match",
        match,
        "--interval",
        str(parsed.options.interval),
    ]
    saved_os = {key: os.environ.get(key) for key in _LLM_ENV_KEYS}
    assist_env = dict(env)
    for key in _LLM_ENV_KEYS:
        env.pop(key, None)
        os.environ.pop(key, None)
    assist = parsed.options.profile == "job-assist"
    watcher = live_watcher
    if assist and watcher is None:
        watcher = LiveWatcher(opencode_runner=opencode_runner, env=assist_env)
    use_tty = sys.stdin.isatty() and sys.stdout.isatty() if tty is None else tty

    def run_user_with_live(argv: list[str]) -> int:
        if "opencode" in argv or any("opencode" in t for t in argv):
            raise RuntimeError("OpenCode must not appear in the user srun argv")
        if watcher is not None:
            watcher.start(run_dir)
            if use_tty and not quiet:
                print(ATTACH_HINT, file=sys.stderr)
        try:
            return run_user(argv)
        finally:
            if watcher is not None:
                watcher.stop()

    try:
        plan = plan_overlap(parsed.passthrough, supervisor)
        code, used = execute_launch(
            plan,
            run_sidecar=run_sidecar,
            run_user=run_user_with_live,
            overlap_ok=overlap_ok,
            passthrough=parsed.passthrough,
            wrap_argv=[*py_mod, "exec-wrap"],
        )
    finally:
        for key, value in saved_os.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if quiet_injected:
            if prev_quiet is None:
                os.environ.pop("AGENT_QUIET", None)
            else:
                os.environ["AGENT_QUIET"] = prev_quiet
    request_agent_stop(run_dir)
    errors = collect_errors or {}
    errors = merge_event_errors(run_dir, errors)
    retry = retry_metadata(
        user_exit=None if (not overlap_ok and used.fallback_used and code == 0) else code,
        overlap_failed_before_start=used.fallback_used and not overlap_ok,
        attempt=1,
    )
    if code != 0:
        retry = retry_metadata(user_exit=code, overlap_failed_before_start=False, attempt=1)
    write_meta(
        run_dir,
        {
            "command": parsed.passthrough,
            "mode": used.mode,
            "collect_errors": errors,
            "exit_code": code,
        },
    )
    summary = summarize_series(run_dir)
    summary["exit_code"] = code
    anomalies = anomalies_from_artifacts(run_dir)
    reason = rollup_reason_code(anomalies, user_exit=code)
    evidence = ["meta.json", "telemetry.json"]
    events_dir = run_dir / "events"
    if events_dir.is_dir():
        evidence.extend(
            sorted(str(p.relative_to(run_dir)) for p in events_dir.iterdir() if p.is_file())
        )
    series_dir = run_dir / "series"
    if series_dir.is_dir():
        evidence.extend(
            sorted(str(p.relative_to(run_dir)) for p in series_dir.glob("*.jsonl"))
        )
        jsonl = list(series_dir.glob("*.jsonl"))
        if jsonl:
            try:
                for path in plot_run(run_dir, plotter=plotter):
                    rel = str(path.relative_to(run_dir)) if path.is_absolute() else str(path)
                    if rel not in evidence:
                        evidence.append(rel)
            except Exception as exc:  # pragma: no cover - plot backend
                errors["plot"] = str(exc)[:500]
    extra: dict[str, Any] = {"collect_errors": errors}
    write_telemetry(
        run_dir,
        summary=summary,
        anomalies=anomalies,
        evidence_paths=evidence,
        reason_code=reason,
        retry_allowed=bool(retry["retry_allowed"]),
        attempt=int(retry["attempt"]),
        extra=extra,
    )
    if parsed.options.profile == "job-assist":
        run_job_assist(
            run_dir,
            user_exit=code,
            opencode_runner=opencode_runner,
        )
        note_path = run_dir / "assist" / "job.json"
        if note_path.is_file():
            try:
                note_summary = json.loads(note_path.read_text(encoding="utf-8")).get("summary") or ""
            except json.JSONDecodeError:
                note_summary = ""
            if note_summary and not quiet:
                print(f"[agent] job-assist: {note_summary}", file=sys.stderr, flush=True)
    return code, run_dir, used


def sbatch_environ(options: AgentOptions) -> dict[str, str]:
    env = {
        "AGENT_PROFILE": options.profile,
        "AGENT_SKILLS": ",".join(options.skills),
    }
    if options.output_dir:
        env["AGENT_JOB_DIR"] = options.output_dir
        env["AGENT_OUTPUT_DIR"] = options.output_dir
    return env


def submit_sbatch(
    script: Path,
    options: AgentOptions,
    *,
    runner: Callable[[list[str], dict[str, str]], int],
    extra_sbatch: list[str] | None = None,
) -> int:
    env = sbatch_environ(options)
    argv = ["sbatch", *(extra_sbatch or []), str(script)]
    return runner(argv, env)
