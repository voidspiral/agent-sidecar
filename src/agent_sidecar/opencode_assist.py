"""Submit-host OpenCode runner for job-assist (no HTTP fallback)."""

from __future__ import annotations

import inspect
import json
import os
import signal
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

DEFAULT_TIMEOUT = 300.0
_POLL = 0.2

Runner = Callable[[list[str], str, float, dict[str, str] | None], tuple[int, str, str]]


class OpenCodeError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def note_summary(path: Path | str | None) -> str:
    if path is None:
        return ""
    note = Path(path)
    if not note.is_file():
        return ""
    try:
        data = json.loads(note.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("summary") or "").strip()


def build_assist_prompt(telemetry: dict[str, Any], run_dir: Path) -> str:
    contract = {
        "summary": telemetry.get("summary") or {},
        "anomalies": telemetry.get("anomalies") or [],
        "reason_code": telemetry.get("reason_code"),
        "evidence_paths": telemetry.get("evidence_paths") or [],
        "run_dir": str(run_dir),
    }
    return (
        "You are job-assist for this HPC SLURM sidecar. "
        "Read only the JSON contract below. Do not scrape /proc. "
        "Do not embed series JSONL bodies. JSONL and PNG are named only via evidence_paths. "
        f"Write {run_dir / 'assist' / 'job.json'} with host=submit, "
        "summary in Simplified Chinese (简体中文), 分条 as a numbered list "
        "(1. 2. 3., one finding per item, not a paragraph): interpret the contract "
        "and include concrete improvement suggestions (srun flags, NFS paths, "
        "--agent-match, interval) inside summary only. suspected_reason copied from reason_code, "
        "actions as an empty list, and evidence_paths from the contract. "
        "If reason_code is execution_error and pid_count is 0, explain in 简体中文 that the job did not "
        "start (missing executable / ENOENT) and propose a corrected agent srun line in summary. "
        "Write that JSON as UTF-8 with raw 简体中文 in summary (not \\uXXXX escapes). "
        "Do not change reason_code. Do not call scancel or scontrol. Do not generate images.\n\n"
        "CONTRACT:\n"
        + json.dumps(contract, sort_keys=True)
    )


def _stop_process(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.terminate()
        except OSError:
            pass
    try:
        proc.wait(timeout=2)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass


def _runner_accepts(runner: Callable[..., Any], name: str) -> bool:
    try:
        params = inspect.signature(runner).parameters
    except (TypeError, ValueError):
        return False
    if name in params:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())


def opencode_run_argv(root: Path | str, prompt: str, *, model: str = "") -> list[str]:
    argv = [
        "opencode",
        "run",
        "--dir",
        str(root),
        "--agent",
        "job-assist",
        "--format",
        "json",
        "--auto",
        prompt,
    ]
    if model:
        auto = argv.index("--auto")
        argv[auto:auto] = ["--model", model]
    return argv


def invoke_runner(
    runner: Callable[..., Any],
    argv: list[str],
    cwd: str,
    timeout: float,
    env: dict[str, str] | None = None,
    note_path: Path | str | None = None,
    cancel: Any | None = None,
) -> tuple[int, str, str]:
    extra: dict[str, Any] = {}
    if _runner_accepts(runner, "note_path"):
        extra["note_path"] = note_path
    if cancel is not None and _runner_accepts(runner, "cancel"):
        extra["cancel"] = cancel
    if extra:
        return runner(argv, cwd, timeout, env, **extra)
    return runner(argv, cwd, timeout, env)


def default_opencode_runner(
    argv: list[str],
    cwd: str,
    timeout: float,
    env: dict[str, str] | None = None,
    note_path: Path | str | None = None,
    cancel: Any | None = None,
) -> tuple[int, str, str]:
    if not argv or shutil.which(argv[0]) is None:
        raise OpenCodeError("opencode_missing", "opencode not on PATH")
    child_env = dict(env) if env is not None else dict(os.environ)
    child_env.setdefault("LANG", "C.UTF-8")
    child_env.setdefault("LC_ALL", "C.UTF-8")
    child_env.setdefault("PYTHONIOENCODING", "utf-8")
    if not child_env.get("ANTHROPIC_API_KEY") and child_env.get("ANTHROPIC_AUTH_TOKEN"):
        child_env["ANTHROPIC_API_KEY"] = child_env["ANTHROPIC_AUTH_TOKEN"]
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=child_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + max(0.0, float(timeout))
    try:
        while True:
            if cancel is not None and getattr(cancel, "is_set", lambda: False)():
                _stop_process(proc)
                raise OpenCodeError("opencode_cancelled", "opencode cancelled")
            if note_summary(note_path):
                _stop_process(proc)
                return 0, "", ""
            rc = proc.poll()
            if rc is not None:
                return rc, "", ""
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _stop_process(proc)
                if note_summary(note_path):
                    return 0, "", ""
                raise OpenCodeError(
                    "opencode_timeout",
                    f"opencode timed out after {timeout}s",
                )
            time.sleep(min(_POLL, remaining))
    except BaseException:
        _stop_process(proc)
        raise


def persist_assist_failure(run_dir: Path, doc: dict[str, Any], code: str, message: str) -> None:
    errors = dict(doc.get("collect_errors") or {})
    errors[code] = message
    doc["collect_errors"] = errors
    (run_dir / "telemetry.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )


def _record_job_assist_success(
    run_dir: Path,
    doc: dict[str, Any],
    summary: str,
) -> None:
    from agent_sidecar.assist import write_job_assist_note

    reason = str(doc.get("reason_code") or "ok")
    write_job_assist_note(
        run_dir,
        reason_code=reason,
        summary=summary,
        evidence_paths=list(doc.get("evidence_paths") or []),
    )
    rel = "assist/job.json"
    evidence = list(doc.get("evidence_paths") or [])
    if rel not in evidence:
        evidence.append(rel)
    doc["evidence_paths"] = evidence
    doc["job_assist"] = [{"path": rel, "host": "submit"}]
    doc["collect_errors"] = dict(doc.get("collect_errors") or {})
    (run_dir / "telemetry.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )


def run_opencode_assist(
    run_dir: Path,
    *,
    user_exit: int,
    opencode_runner: Runner | None = None,
    repo_root: Path | None = None,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
) -> int:
    from agent_sidecar.telemetry import load_telemetry

    doc = load_telemetry(run_dir)
    timeout = (
        timeout
        if timeout is not None
        else float(os.environ.get("AGENT_OPENCODE_TIMEOUT") or DEFAULT_TIMEOUT)
    )
    root = repo_root or default_repo_root()
    prompt = build_assist_prompt(doc, run_dir)
    argv = opencode_run_argv(
        root, prompt, model=os.environ.get("AGENT_OPENCODE_MODEL") or ""
    )
    send = opencode_runner or default_opencode_runner
    note_path = run_dir / "assist" / "job.json"
    rc, stdout, stderr = 0, "", ""
    try:
        rc, stdout, stderr = invoke_runner(
            send, argv, str(root), timeout, env, note_path=note_path
        )
    except OpenCodeError as exc:
        summary = note_summary(note_path)
        if summary:
            _record_job_assist_success(run_dir, doc, summary)
            return user_exit
        persist_assist_failure(run_dir, doc, exc.code, exc.message)
        return user_exit
    summary = note_summary(note_path)
    if not summary:
        summary = (stdout or "").strip()
    if rc != 0 and not summary:
        persist_assist_failure(
            run_dir,
            doc,
            "opencode_failed",
            (stderr or stdout or f"opencode exit {rc}")[:500],
        )
        return user_exit
    if not summary:
        persist_assist_failure(
            run_dir,
            doc,
            "opencode_failed",
            ((stderr or stdout or "OpenCode wrote no assist/job.json")[:500]),
        )
        return user_exit
    _record_job_assist_success(run_dir, doc, summary)
    return user_exit
