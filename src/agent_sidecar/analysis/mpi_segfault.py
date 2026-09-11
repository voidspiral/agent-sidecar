"""mpi_segfault analysis pack."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agent_sidecar.analysis.mpi_abort import SOURCE_LINE_CITE_RE, ask_code_command

FAULT_RANK_RE = re.compile(r"rank\s+(\d+)\s+segfault", re.IGNORECASE)
SIGNAL_RE = re.compile(
    r"(?:signal\s*(\d+)|SIGSEGV|Segmentation\s+fault)",
    re.IGNORECASE,
)


def _read_stderr(run_dir: Path) -> str:
    path = run_dir / "events" / "stderr.tail"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_segfault(text: str) -> tuple[int | None, int | None]:
    rank: int | None = None
    signal: int | None = None
    m = FAULT_RANK_RE.search(text)
    if m:
        rank = int(m.group(1))
    if rank is None:
        m2 = re.search(
            r"(?:rank|Rank)\s+(\d+).{0,80}(?:signal\s*11|SIGSEGV|Segmentation)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if m2:
            rank = int(m2.group(1))
    sm = SIGNAL_RE.search(text)
    if sm:
        if sm.group(1):
            signal = int(sm.group(1))
        else:
            signal = 11
    elif re.search(r"segfault", text, re.IGNORECASE):
        signal = 11
    return rank, signal


def _series_brief(run_dir: Path) -> dict[str, Any]:
    series = run_dir / "series"
    files = list(series.glob("*.jsonl")) if series.is_dir() else []
    if not files:
        return {"pid_count": 0, "note": "启动后很快段错误，序列不足"}
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


def build_mpi_segfault_analysis(
    run_dir: Path,
    *,
    reason_code: str,
    summary: dict[str, Any],
    code_hits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    stderr = _read_stderr(run_dir)
    rank, signal = _parse_segfault(stderr)
    lines = [ln for ln in stderr.splitlines() if ln.strip()]
    excerpt = lines[-20:] if len(lines) > 20 else lines
    series = _series_brief(run_dir)
    hits = list(code_hits or [])
    needs_source = len(hits) == 0
    ask_cmd = ask_code_command(run_dir)
    return {
        "pack": "mpi_segfault",
        "reason_code": reason_code,
        "fault_rank": rank,
        "signal": signal,
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
            "检查 fault_rank 对应源码中的空指针 / 越界访问",
            "确认该 rank 是否在通信完成后本地崩溃（非 MPI_Abort）",
            "用相同 --agent-match 复现：agent srun ... -- /path/to/mpi_fault_segfault",
            f"尚未授权源码时请执行：{ask_cmd}",
            f"需要模型解读时可再加 --llm：{ask_cmd} --llm",
        ],
    }


def chinese_summary(analysis: dict[str, Any]) -> str:
    rank = analysis.get("fault_rank")
    signal = analysis.get("signal")
    series = analysis.get("series") or {}
    rank_s = str(rank) if rank is not None else "未解析"
    sig_s = str(signal) if signal is not None else "未解析"
    ask = str(
        analysis.get("ask_code_cmd")
        or "python3 -m agent_sidecar analy --run-dir <run_dir> --code /path/to/src"
    )
    items = [
        f"1. 结论：检测到 MPI 段错误（reason_code=mpi_segfault），"
        f"fault_rank={rank_s}，signal={sig_s}",
        (
            f"2. 采集：pid_count={series.get('pid_count')}，"
            f"cpu_peak={series.get('cpu_peak')}，rss_peak_mb={series.get('rss_peak_mb')}"
            + (f"；{series['note']}" if series.get("note") else "")
        ),
        "3. 异常：stderr 含 segfault/SIGSEGV/signal 11 类文本，见 events/stderr.tail "
        "与 analysis.json 摘录；可能原因（待验证）：空指针 / 越界 / 未初始化指针",
    ]
    hits = analysis.get("code_hits") or []
    if hits:
        loc = hits[0]
        items.append(
            "4. 建议：核对 fault rank 附近的指针与数组边界；"
            "用相同 --agent-match 在共享路径复现"
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


__all__ = [
    "SOURCE_LINE_CITE_RE",
    "ask_code_command",
    "build_mpi_segfault_analysis",
    "chinese_summary",
]
