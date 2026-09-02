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

Runner = Callable[[list[str]], int]

_LLM_ENV_KEYS = (
    "AGENT_LLM_API_KEY",
    "AGENT_LLM_BASE_URL",
    "AGENT_LLM_MODEL",
    "AGENT_LLM_TIMEOUT",
)


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
) -> tuple[int, Path, LaunchPlan]:
    out_root = resolve_output_dir(parsed.options, env)
    run_dir = out_root / make_run_id(pid=0)
    ensure_run_layout(run_dir)
    src_dir = str(Path(__file__).resolve().parents[1])
    exe = sys.executable
    py_mod = [
        "env",
        "-u",
        "AGENT_LLM_API_KEY",
        "-u",
        "AGENT_LLM_BASE_URL",
        "-u",
        "AGENT_LLM_MODEL",
        "-u",
        "AGENT_LLM_TIMEOUT",
        f"PYTHONPATH={src_dir}",
        "PYTHONUNBUFFERED=1",
        exe,
        "-m",
        "agent_sidecar",
    ]
    supervisor = [
        *py_mod,
        "supervisor",
        "--job-id",
        env.get("SLURM_JOB_ID", "0"),
        "--output-dir",
        str(run_dir),
        "--skills",
        ",".join(parsed.options.skills) or "proc-monitor",
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
