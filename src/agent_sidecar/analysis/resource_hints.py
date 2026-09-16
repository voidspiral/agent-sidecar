"""Deterministic Chinese job-assist notes from JobTelemetry summary."""

from __future__ import annotations

from typing import Any

from pathlib import Path

CPU_LOW = 10.0
CPU_HIGH = 80.0
IO_HEAVY_BPS = 1_000_000.0


def _fmt(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def suggestion_clauses(summary: dict[str, Any]) -> list[str]:
    pid_count = int(summary.get("pid_count") or 0)
    exit_code = summary.get("exit_code")
    cpu_peak = summary.get("cpu_peak")
    io_r = float(summary.get("io_read_bps_sum") or 0)
    io_w = float(summary.get("io_write_bps_sum") or 0)
    eth_rx = summary.get("eth_rx_bps_peak")
    eth_tx = summary.get("eth_tx_bps_peak")
    out: list[str] = []
    if pid_count == 0:
        out.append(
            "未采到用户进程，请检查 --agent-match、PYTHONPATH 与 events/mpi_monitor_import.err"
        )
        if exit_code not in (0, None):
            out.append("用户退出码非 0，同时核对二进制是否在共享路径")
    elif cpu_peak is not None:
        peak = float(cpu_peak)
        if peak < CPU_LOW:
            out.append(
                "CPU 峰值偏低，作业可能过短或未吃满核，可减小 --interval 或核对 match"
            )
        elif peak >= CPU_HIGH:
            out.append("CPU 峰值偏高，计算密集，请核对 --cpus-per-task")
    if pid_count > 0 and (io_r + io_w) >= IO_HEAVY_BPS:
        peak = float(cpu_peak) if cpu_peak is not None else 0.0
        if peak < CPU_HIGH:
            out.append(
                "IO 相对突出，注意共享存储路径与 Lustre 条带，勿编造未采集的 OST 数据"
            )
    if eth_rx is not None or eth_tx is not None:
        out.append("以太网峰值是主机 NIC 速率，不是 MPI 消息字节")
    if not out:
        out.append("采样正常，可保持当前 srun 与 --interval")
    return out


def chinese_summary(doc: dict[str, Any]) -> str:
    summary = dict(doc.get("summary") or {})
    reason = str(doc.get("reason_code") or "ok")
    anomalies = doc.get("anomalies") or []
    pid_count = int(summary.get("pid_count") or 0)
    started = "已采到用户进程" if pid_count > 0 else "未采到用户 PID"
    exit_code = summary.get("exit_code")
    items = [
        f"1. 结论：reason_code={reason}，exit_code={_fmt(exit_code)}，{started}。",
        (
            "2. 采集："
            f"host_count={_fmt(summary.get('host_count'))} "
            f"pid_count={_fmt(pid_count)} "
            f"cpu_avg={_fmt(summary.get('cpu_avg'))} "
            f"cpu_peak={_fmt(summary.get('cpu_peak'))} "
            f"rss_peak_mb={_fmt(summary.get('rss_peak_mb'))} "
            f"io_read_bps_sum={_fmt(summary.get('io_read_bps_sum'))} "
            f"io_write_bps_sum={_fmt(summary.get('io_write_bps_sum'))} "
            f"eth_rx_bps_peak={_fmt(summary.get('eth_rx_bps_peak'))} "
            f"eth_tx_bps_peak={_fmt(summary.get('eth_tx_bps_peak'))}。"
        ),
    ]
    if anomalies:
        codes = ",".join(str(a.get("reason_code") or "") for a in anomalies if isinstance(a, dict))
        items.append(f"3. 异常：{codes or '见 telemetry anomalies'}。")
    else:
        items.append("3. 异常：无工具异常。")
    items.append("4. 建议：" + "；".join(suggestion_clauses(summary)))
    return "\n".join(items)


def write_resource_hints_note(run_dir: Path) -> Path:
    from agent_sidecar.opencode_assist import _record_job_assist_success
    from agent_sidecar.telemetry import load_telemetry

    doc = load_telemetry(run_dir)
    summary = chinese_summary(doc)
    _record_job_assist_success(run_dir, doc, summary)
    return run_dir / "assist" / "job.json"
