"""Submit-host OpenCode runner for job-assist (no HTTP fallback)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

DEFAULT_TIMEOUT = 120.0

Runner = Callable[[list[str], str, float, dict[str, str] | None], tuple[int, str, str]]


class OpenCodeError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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
        "summary set to your interpretation, suspected_reason copied from reason_code, "
        "actions as an empty list, and evidence_paths from the contract. "
        "If reason_code is execution_error and pid_count is 0, explain that the job did not "
        "start (missing executable / ENOENT) and propose a corrected agent srun line in summary. "
        "Do not change reason_code. Do not call scancel or scontrol. Do not generate images.\n\n"
        "CONTRACT:\n"
        + json.dumps(contract, sort_keys=True)
    )


def default_opencode_runner(
    argv: list[str],
    cwd: str,
    timeout: float,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    if not argv or shutil.which(argv[0]) is None:
        raise OpenCodeError("opencode_missing", "opencode not on PATH")
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            text=True,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise OpenCodeError("opencode_timeout", str(exc)) from exc
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def persist_assist_failure(run_dir: Path, doc: dict[str, Any], code: str, message: str) -> None:
    errors = dict(doc.get("collect_errors") or {})
    errors[code] = message
    doc["collect_errors"] = errors
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
    from agent_sidecar.assist import write_job_assist_note
    from agent_sidecar.telemetry import load_telemetry

    doc = load_telemetry(run_dir)
    timeout = (
        timeout
        if timeout is not None
        else float(os.environ.get("AGENT_OPENCODE_TIMEOUT") or DEFAULT_TIMEOUT)
    )
    root = repo_root or default_repo_root()
    prompt = build_assist_prompt(doc, run_dir)
    argv = ["opencode", "run", "--dir", str(root), prompt]
    send = opencode_runner or default_opencode_runner
    try:
        rc, stdout, stderr = send(argv, str(root), timeout, env)
    except OpenCodeError as exc:
        persist_assist_failure(run_dir, doc, exc.code, exc.message)
        return user_exit
    if rc != 0:
        persist_assist_failure(
            run_dir,
            doc,
            "opencode_failed",
            (stderr or stdout or f"opencode exit {rc}")[:500],
        )
        return user_exit
    reason = str(doc.get("reason_code") or "ok")
    note_path = run_dir / "assist" / "job.json"
    summary = ""
    if note_path.is_file():
        try:
            existing = json.loads(note_path.read_text(encoding="utf-8"))
            summary = str(existing.get("summary") or "")
        except json.JSONDecodeError:
            summary = ""
    if not summary:
        summary = (stdout or "").strip()
    if not summary:
        persist_assist_failure(run_dir, doc, "opencode_failed", "OpenCode wrote no assist/job.json")
        return user_exit
    rel = "assist/job.json"
    write_job_assist_note(
        run_dir,
        reason_code=reason,
        summary=summary,
        evidence_paths=list(doc.get("evidence_paths") or []),
    )
    evidence = list(doc.get("evidence_paths") or [])
    if rel not in evidence:
        evidence.append(rel)
    doc["evidence_paths"] = evidence
    doc["job_assist"] = [{"path": rel, "host": "submit"}]
    doc["collect_errors"] = dict(doc.get("collect_errors") or {})
    (run_dir / "telemetry.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )
    return user_exit
