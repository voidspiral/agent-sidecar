"""Run deterministic analysis packs; optionally OpenCode with --llm."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agent_sidecar.analysis.code_scan import scan_code_root
from agent_sidecar.analysis import launch_fail as launch_fail_pack
from agent_sidecar.analysis import mpi_abort as mpi_abort_pack
from agent_sidecar.analysis.packs import select_pack
from agent_sidecar.assist import write_job_assist_note
from agent_sidecar.telemetry import (
    anomalies_from_artifacts,
    load_telemetry,
    rollup_reason_code,
    summarize_series,
    write_telemetry,
)

Runner = Callable[..., tuple[int, str, str]]


def _ensure_telemetry(run_dir: Path) -> dict[str, Any]:
    tel_path = run_dir / "telemetry.json"
    if tel_path.is_file():
        return load_telemetry(run_dir)
    summary = summarize_series(run_dir)
    anomalies = anomalies_from_artifacts(run_dir)
    exit_code = int(summary.get("exit_code") or 1)
    reason = rollup_reason_code(anomalies, user_exit=exit_code)
    evidence = ["telemetry.json"]
    for folder in ("events", "series", "assist"):
        d = run_dir / folder
        if not d.is_dir():
            continue
        for path in sorted(d.iterdir()):
            if path.is_file():
                evidence.append(str(path.relative_to(run_dir)))
    write_telemetry(
        run_dir,
        summary=summary,
        anomalies=anomalies,
        evidence_paths=evidence,
        reason_code=reason,
        retry_allowed=False,
        attempt=1,
    )
    return load_telemetry(run_dir)


def _merge_evidence(doc: dict[str, Any], *rels: str) -> None:
    paths = list(doc.get("evidence_paths") or [])
    for rel in rels:
        if rel and rel not in paths:
            paths.append(rel)
    doc["evidence_paths"] = paths


def _write_analysis(run_dir: Path, analysis: dict[str, Any]) -> Path:
    assist = run_dir / "assist"
    assist.mkdir(parents=True, exist_ok=True)
    path = assist / "analysis.json"
    path.write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def _refresh_telemetry_evidence(run_dir: Path, doc: dict[str, Any], *rels: str) -> None:
    _merge_evidence(doc, *rels)
    if "job_assist" not in doc and (run_dir / "assist" / "job.json").is_file():
        doc["job_assist"] = [{"path": "assist/job.json", "host": "submit"}]
        _merge_evidence(doc, "assist/job.json")
    (run_dir / "telemetry.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def run_analysis(
    run_dir: Path,
    *,
    code_root: Path | str | None = None,
    use_llm: bool = False,
    opencode_runner: Runner | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    doc = _ensure_telemetry(run_dir)
    reason = str(doc.get("reason_code") or "execution_error")
    summary = dict(doc.get("summary") or {})
    pack = select_pack(reason, summary)

    code_hits: list[dict[str, Any]] = []
    if code_root is not None:
        code_hits = scan_code_root(Path(code_root))

    if pack == "mpi_abort":
        analysis = mpi_abort_pack.build_mpi_abort_analysis(
            run_dir, reason_code=reason, summary=summary, code_hits=code_hits
        )
        zh = mpi_abort_pack.chinese_summary(analysis)
    elif pack == "launch_fail":
        analysis = launch_fail_pack.build_launch_fail_analysis(
            reason_code=reason, summary=summary
        )
        zh = launch_fail_pack.chinese_summary(analysis)
    else:
        analysis = {
            "pack": pack,
            "reason_code": reason,
            "code_hits": code_hits,
            "note": "no dedicated pack in this release",
            "suggestions": ["查看 telemetry.json anomalies 与 events/"],
        }
        zh = (
            f"1. 结论：reason_code={reason}（pack={pack}）\n"
            "2. 采集：见 telemetry summary\n"
            "3. 异常：尚无专用 pack，请查看 events/ 与 anomalies\n"
            "4. 建议：保留 run_dir 并用 agent analy --run-dir 复查"
        )

    _write_analysis(run_dir, analysis)
    job_path = run_dir / "assist" / "job.json"
    wrote_job = False
    # When --llm is requested, leave job.json for OpenCode; otherwise fill if missing.
    if not use_llm and not job_path.is_file():
        write_job_assist_note(
            run_dir,
            reason_code=reason,
            summary=zh,
            evidence_paths=list(doc.get("evidence_paths") or [])
            + ["assist/analysis.json"],
        )
        wrote_job = True

    _refresh_telemetry_evidence(
        run_dir,
        doc,
        "assist/analysis.json",
        "assist/job.json" if wrote_job or job_path.is_file() else "",
    )

    if use_llm and opencode_runner is not None:
        from agent_sidecar.opencode_assist import run_opencode_assist

        # Avoid pack note short-circuiting default_opencode_runner's note_summary poll.
        if job_path.is_file():
            job_path.unlink()
        run_opencode_assist(
            run_dir,
            user_exit=int(summary.get("exit_code") or 1),
            opencode_runner=opencode_runner,
            env=env,
        )
        if not job_path.is_file():
            write_job_assist_note(
                run_dir,
                reason_code=reason,
                summary=zh,
                evidence_paths=list(doc.get("evidence_paths") or [])
                + ["assist/analysis.json"],
            )
            _refresh_telemetry_evidence(run_dir, load_telemetry(run_dir), "assist/job.json")

    return {"pack": pack, "reason_code": reason, "analysis": analysis}
