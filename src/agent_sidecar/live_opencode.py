"""Submit-host live OpenCode watcher (ticks on artifact snapshots, not /proc)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable

from agent_sidecar.opencode_assist import (
    DEFAULT_TIMEOUT,
    OpenCodeError,
    default_opencode_runner,
    default_repo_root,
    invoke_runner,
    note_summary,
    opencode_run_argv,
)
from agent_sidecar.telemetry import anomalies_from_artifacts, summarize_series

DEFAULT_LIVE_INTERVAL = 15.0
ATTACH_HINT = (
    "[agent] live OpenCode: attach from a second terminal "
    "(opencode attach); this srun TTY stays with the user step"
)

Runner = Callable[[list[str], str, float, dict[str, str] | None], tuple[int, str, str]]


def live_timeout(value: float | None = None, env: dict[str, str] | None = None) -> float:
    if value is not None:
        return float(value)
    raw = (env or os.environ).get("AGENT_OPENCODE_TIMEOUT") or ""
    if raw:
        try:
            return float(raw)
        except ValueError:
            return DEFAULT_TIMEOUT
    return DEFAULT_TIMEOUT


def live_interval(value: float | None = None, env: dict[str, str] | None = None) -> float:
    if value is not None:
        return float(value)
    raw = (env or os.environ).get("AGENT_OPENCODE_LIVE_INTERVAL") or ""
    if raw:
        try:
            return float(raw)
        except ValueError:
            return DEFAULT_LIVE_INTERVAL
    return DEFAULT_LIVE_INTERVAL


def build_live_prompt(
    summary: dict[str, Any],
    anomalies: list[dict[str, Any]],
    evidence_paths: list[str],
    run_dir: Path,
) -> str:
    contract = {
        "summary": summary,
        "anomalies": anomalies,
        "evidence_paths": evidence_paths,
        "run_dir": str(run_dir),
        "phase": "live",
    }
    return (
        "You are job-assist watching a running HPC SLURM job. "
        "Read only the JSON snapshot below. Do not scrape /proc. "
        "Do not embed series JSONL bodies. JSONL files are named only via evidence_paths. "
        f"Write {run_dir / 'assist' / 'live.json'} with host=submit, "
        "summary in Simplified Chinese (简体中文), 分条 as a numbered list "
        "(1. 2. 3., one finding per item, not a paragraph): interpret the snapshot "
        "and include concrete improvement suggestions (srun flags, NFS paths, "
        "--agent-match, interval) inside summary only. suspected_reason from anomalies if any else ok. "
        "actions MUST be an empty list. "
        "Write that JSON as UTF-8 with raw 简体中文 in summary (not \\uXXXX escapes). "
        "Do not change reason_code. Do not call scancel or scontrol. "
        "Do not generate images.\n\n"
        "SNAPSHOT:\n"
        + json.dumps(contract, sort_keys=True)
    )


def _evidence_paths(run_dir: Path) -> list[str]:
    out: list[str] = []
    for folder in ("series", "events", "assist"):
        d = run_dir / folder
        if not d.is_dir():
            continue
        for path in sorted(d.iterdir()):
            if path.is_file():
                out.append(str(path.relative_to(run_dir)))
    return out


def _anomaly_hash(anomalies: list[dict[str, Any]]) -> str:
    blob = json.dumps(anomalies, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class LiveWatcher:
    def __init__(
        self,
        *,
        opencode_runner: Runner | None = None,
        interval: float | None = None,
        env: dict[str, str] | None = None,
        repo_root: Path | None = None,
        timeout: float | None = None,
    ) -> None:
        self.interval = live_interval(interval, env)
        self._runner = opencode_runner or default_opencode_runner
        self._env = env
        self._root = repo_root or default_repo_root()
        self._timeout = live_timeout(timeout, env)
        self._run_dir: Path | None = None
        self._stopped = True
        self._last_hash: str | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._cancel = threading.Event()

    def start(self, run_dir: Path) -> None:
        self._run_dir = run_dir
        self._stopped = False
        self._last_hash = None
        self._stop_event.clear()
        self._cancel.clear()
        (run_dir / "assist").mkdir(parents=True, exist_ok=True)
        (run_dir / "events").mkdir(parents=True, exist_ok=True)
        if self.interval > 0:
            self._thread = threading.Thread(target=self._loop, name="live-opencode", daemon=True)
            self._thread.start()

    def tick(self) -> str | None:
        if self._stopped or self._run_dir is None:
            return None
        run_dir = self._run_dir
        summary = summarize_series(run_dir)
        anomalies = anomalies_from_artifacts(run_dir)
        if not anomalies:
            return None
        digest = _anomaly_hash(anomalies)
        if digest == self._last_hash:
            return None
        self._last_hash = digest
        evidence = _evidence_paths(run_dir)
        prompt = build_live_prompt(summary, anomalies, evidence, run_dir)
        argv = opencode_run_argv(
            self._root,
            prompt,
            model=(self._env or os.environ).get("AGENT_OPENCODE_MODEL") or "",
        )
        note_path = run_dir / "assist" / "live.json"
        try:
            rc, stdout, stderr = invoke_runner(
                self._runner,
                argv,
                str(self._root),
                self._timeout,
                self._env,
                note_path=note_path,
                cancel=self._cancel,
            )
        except OpenCodeError as exc:
            if exc.code == "opencode_cancelled":
                return prompt
            summary_text = note_summary(note_path)
            if not summary_text:
                (run_dir / "events" / f"{exc.code}.err").write_text(
                    exc.message + "\n", encoding="utf-8"
                )
                return prompt
            rc, stdout, stderr = 0, "", ""
        else:
            summary_text = note_summary(note_path)
        if rc != 0 and not summary_text:
            (run_dir / "events" / "opencode_failed.err").write_text(
                (stderr or stdout or f"opencode exit {rc}")[:500] + "\n",
                encoding="utf-8",
            )
            return prompt
        if not summary_text:
            summary_text = (stdout or "").strip() or "live snapshot"
        suspected = str(anomalies[0]["reason_code"]) if anomalies else "ok"
        note = {
            "host": "submit",
            "summary": summary_text,
            "suspected_reason": suspected,
            "evidence_paths": evidence,
            "confidence": None,
            "actions": [],
        }
        note_path.write_text(
            json.dumps(note, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        if (self._env or os.environ).get("AGENT_QUIET") != "1":
            print(f"[agent] live-assist: {summary_text}", file=sys.stderr, flush=True)
        return prompt

    def stop(self) -> None:
        self._stopped = True
        self._cancel.set()
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=8)
        self._thread = None

    def _loop(self) -> None:
        while not self._stopped:
            try:
                self.tick()
            except Exception:
                return
            if self._stop_event.wait(self.interval):
                return
