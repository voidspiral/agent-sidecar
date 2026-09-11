"""mpi_abort analysis pack."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

RANK_RE = re.compile(
    r"(?:rank\s+|on\s+rank\s+)(\d+)|MPI_Abort[^\n]*rank\s+(\d+)",
    re.IGNORECASE,
)
ERR_RE = re.compile(r"errorcode\s*=\s*(-?\d+)", re.IGNORECASE)
# Phase-1 notes must not look like path:lineno cites (e.g. foo.c:59).
SOURCE_LINE_CITE_RE = re.compile(r"\.\w+:\d+")


def ask_code_command(run_dir: Path) -> str:
    return (
        f"python3 -m agent_sidecar analy --run-dir {run_dir} "
        "--code /path/to/src"
    )


def _read_stderr(run_dir: Path) -> str:
    path = run_dir / "events" / "stderr.tail"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_abort(text: str) -> tuple[int | None, int | None]:
    rank: int | None = None
    err: int | None = None
    for line in text.splitlines():
        if "MPI_Abort" not in line and "mpi_abort" not in line.lower():
            if "Abort" not in line:
                continue
        m = RANK_RE.search(line)
        if m:
            raw = m.group(1) or m.group(2)
            if raw is not None:
                rank = int(raw)
        em = ERR_RE.search(line)
        if em:
            err = int(em.group(1))
        if "MPI_Abort" in line and rank is None:
            m2 = re.search(r"\brank\s+(\d+)\b", line, re.IGNORECASE)
            if m2:
                rank = int(m2.group(1))
    if rank is None:
        m3 = re.search(r"rank\s+(\d+)\s+called\s+MPI_Abort", text, re.IGNORECASE)
        if m3:
            rank = int(m3.group(1))
    if err is None:
        em2 = ERR_RE.search(text)
        if em2:
            err = int(em2.group(1))
    return rank, err


def _series_brief(run_dir: Path) -> dict[str, Any]:
    series = run_dir / "series"
    files = list(series.glob("*.jsonl")) if series.is_dir() else []
    if not files:
        return {"pid_count": 0, "note": "启动后很快 abort，序列不足"}
    cpu: list[float] = []
    rss: list[float] = []
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if "cpu_pct" in rec:
                cpu.append(float(rec["cpu_pct"]))
            if "rss_mb" in rec:
                rss.append(float(rec["rss_mb"]))
    return {
        "pid_count": len(files),
        "cpu_peak": max(cpu) if cpu else None,
        "rss_peak_mb": max(rss) if rss else None,
        "note": None,
    }


def build_mpi_abort_analysis(
    run_dir: Path,
    *,
    reason_code: str,
    summary: dict[str, Any],
    code_hits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    stderr = _read_stderr(run_dir)
    rank, errorcode = _parse_abort(stderr)
    lines = [ln for ln in stderr.splitlines() if ln.strip()]
    excerpt = lines[-20:] if len(lines) > 20 else lines
    series = _series_brief(run_dir)
    hits = list(code_hits or [])
    needs_source = len(hits) == 0
    ask_cmd = ask_code_command(run_dir)
    return {
        "pack": "mpi_abort",
        "reason_code": reason_code,
        "abort_rank": rank,
        "errorcode": errorcode,
        "stderr_excerpt": excerpt,
        "series": series,
        "summary_numbers": {
            "host_count": summary.get("host_count"),
            "pid_count": summary.get("pid_count"),
            "exit_code": summary.get("exit_code"),
        },
        "code_hits": hits,
        "needs_source": needs_source,
        "ask_code_cmd": ask_cmd,
        "suggestions": [
            "检查 abort_rank 对应源码中的 MPI_Abort 调用与 errorcode",
            "确认该 rank 是否在通信/IO/断言失败路径上",
            "用相同 --agent-match 复现：agent srun ... -- /path/to/mpi_fault_abort",
            f"尚未授权源码时请执行：{ask_cmd}",
            f"需要模型解读时可再加 --llm：{ask_cmd} --llm",
        ],
    }


def chinese_summary(analysis: dict[str, Any]) -> str:
    rank = analysis.get("abort_rank")
    err = analysis.get("errorcode")
    series = analysis.get("series") or {}
    rank_s = str(rank) if rank is not None else "未解析"
    err_s = str(err) if err is not None else "未解析"
    ask = str(analysis.get("ask_code_cmd") or "python3 -m agent_sidecar analy --run-dir <run_dir> --code /path/to/src")
    items = [
        f"1. 结论：检测到 MPI_Abort（reason_code=mpi_abort），abort_rank={rank_s}，errorcode={err_s}",
        (
            f"2. 采集：pid_count={series.get('pid_count')}，"
            f"cpu_peak={series.get('cpu_peak')}，rss_peak_mb={series.get('rss_peak_mb')}"
            + (f"；{series['note']}" if series.get("note") else "")
        ),
        "3. 异常：stderr 含 MPI_Abort 文本，见 events/stderr.tail 与 analysis.json 摘录；"
        "可能原因（待验证）：显式错误处理 / 断言失败 / 通信异常后 Abort",
    ]
    hits = analysis.get("code_hits") or []
    if hits:
        loc = hits[0]
        items.append(
            "4. 建议：核对 abort rank 的错误路径；用相同 --agent-match 在共享路径复现"
        )
        items.append(
            "5. 源码命中（用户授权路径）："
            f"{loc.get('path')}:{loc.get('lineno')} → {loc.get('line', '').strip()}"
        )
    else:
        items.append(
            "4. 建议：尚未做源码级定位。请提供应用源码目录后执行："
            f"`{ask}`；需要模型解读时可再加 `--llm`：`{ask} --llm`；不要臆造 file:line"
        )
    return "\n".join(items)
