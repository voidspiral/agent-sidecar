"""Run a wrapped srun and preserve the user exit code."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_sidecar.argv import AgentOptions, ParsedArgv
from agent_sidecar.assist import run_job_assist
from agent_sidecar.launch import LaunchPlan, execute_launch, plan_overlap
from agent_sidecar.llm import load_llm_config
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
    raw = options.output_dir or env.get("AGENT_JOB_DIR") or "runs"
    return Path(raw)


def sidecar_pythonpath(src_dir: str, env: dict[str, str]) -> str:
    mpi = env.get("AGENT_MPI_MONITOR_SRC") or DEFAULT_MPI_MONITOR_SRC
    return f"{src_dir}:{mpi}"


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


def resolve_output_dir(options: AgentOptions, env: dict[str, str]) -> Path:
    raw = options.output_dir or env.get("AGENT_JOB_DIR") or "runs"
    return Path(raw)


def wrap_srun(
    parsed: ParsedArgv,
    *,
    env: dict[str, str],
    run_sidecar: Runner,
    run_user: Runner,
    overlap_ok: bool = True,
    collect_errors: dict[str, str] | None = None,
    llm_transport=None,
    plotter=None,
) -> tuple[int, Path, LaunchPlan]:
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
    llm_cfg = load_llm_config(parsed.options, env)
    saved_os = {key: os.environ.get(key) for key in _LLM_ENV_KEYS}
    for key in _LLM_ENV_KEYS:
        env.pop(key, None)
        os.environ.pop(key, None)
    try:
        plan = plan_overlap(parsed.passthrough, supervisor)
        code, used = execute_launch(
            plan,
            run_sidecar=run_sidecar,
            run_user=run_user,
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
            cfg=llm_cfg,
            user_exit=code,
            transport=llm_transport,
        )
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
