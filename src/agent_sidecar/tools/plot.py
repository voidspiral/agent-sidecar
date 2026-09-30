"""Optional PNG plots; JSONL remains if matplotlib is missing."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from agent_sidecar.chart_markers import load_markers, markers_in_range
from agent_sidecar.live_plot import eth_label, series_label

X_LABEL = "已运行时间 (s)"
AXIS = {
    "cpu_pct": ("CPU %", "CPU (%)", True),
    "rss_mb": ("RSS MB", "RSS (MB)", False),
    "io_read_bps": ("IO read B/s", "read (B/s)", True),
    "io_write_bps": ("IO write B/s", "write (B/s)", True),
    "eth_rx_bps": ("以太网接收 B/s", "以太网接收 (B/s)", True),
    "eth_tx_bps": ("以太网发送 B/s", "以太网发送 (B/s)", True),
    "tcp_rx_bps": ("TCP 接收 B/s", "TCP 接收 (B/s)", True),
    "tcp_tx_bps": ("TCP 发送 B/s", "TCP 发送 (B/s)", True),
}
_CJK_FONTS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)
_cjk_ready = False

MARKER_COLORS = {
    "mpi_abort": "#c0392b",
    "mpi_segfault": "#d35400",
    "slurm_oom": "#8e44ad",
    "node_local": "#f1c40f",
}


def plot_run(run_dir: Path, *, plotter=None, net_plotter=None) -> list[Path]:
    """Write charts if a plotter is available. Never delete JSONL."""
    series = run_dir / "series"
    pid_files = (
        [
            path
            for path in series.glob("*_pid*.jsonl")
            if not path.name.endswith("_net.jsonl")
        ]
        if series.is_dir()
        else []
    )
    net_files = list(series.glob("*_net.jsonl")) if series.is_dir() else []
    if plotter is None:
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            plotter = None
        else:
            plotter = _default_plotter
    charts = run_dir / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if plotter is not None:
        for path in pid_files:
            written.extend(plotter(path, charts))
    if net_files:
        written.extend(_plot_net(run_dir, net_plotter=net_plotter))
    return written


def annotate_chart(ax: Any, xs: list[float], markers: list[dict[str, Any]]) -> None:
    """Draw in-range vertical markers on a matplotlib axis (absolute epoch x)."""
    samples = [float(x) for x in xs]
    visible = markers_in_range(markers, samples)
    if not visible or not samples:
        return
    lo = min(samples)
    hi = max(samples)
    right = max(hi, max(float(rec["ts"]) for rec in visible))
    if hasattr(ax, "set_xlim"):
        ax.set_xlim(lo, right)
    _ymin, ymax = ax.get_ylim()
    for rec in visible:
        ts = float(rec["ts"])
        color = MARKER_COLORS.get(str(rec.get("reason_code") or ""), "#7f8c8d")
        ax.axvline(ts, color=color, linestyle="--", linewidth=1.4, zorder=3)
        label = f"{rec.get('host') or ''} {rec.get('reason_code') or ''}".strip()
        ax.text(
            ts,
            ymax,
            label,
            rotation=90,
            va="top",
            ha="right",
            fontsize=7,
            color=color,
            clip_on=True,
        )


def elapsed_xs(xs: list[float]) -> tuple[float, list[float]]:
    t0 = float(xs[0]) if xs else 0.0
    return t0, [float(x) - t0 for x in xs]


def shift_markers(markers: list[dict[str, Any]], t0: float) -> list[dict[str, Any]]:
    shifted: list[dict[str, Any]] = []
    for rec in markers:
        item = dict(rec)
        item["ts"] = float(rec["ts"]) - t0
        shifted.append(item)
    return shifted


def legend_from_chart(path: Path) -> str:
    stem = path.stem
    for metric in AXIS:
        suffix = f"_{metric}"
        if not stem.endswith(suffix):
            continue
        body = stem[: -len(suffix)]
        if "_pid" in body:
            host, _sep, pid_s = body.rpartition("_pid")
            return series_label(host, int(pid_s), None)
        host, _sep, iface = body.partition("_")
        if iface:
            return eth_label(host, iface)
        return body
    return stem


def legend_from_rows(rows: list[dict[str, Any]]) -> str:
    host = str(rows[0].get("host") or "")
    pid = int(rows[0]["pid"])
    rank_raw = rows[0].get("rank")
    rank = int(rank_raw) if rank_raw is not None else None
    return series_label(host, pid, rank)


def _ensure_cjk() -> None:
    global _cjk_ready
    if _cjk_ready:
        return
    _cjk_ready = True
    try:
        from matplotlib import font_manager
        import matplotlib.pyplot as plt
    except ImportError:
        return
    for path in _CJK_FONTS:
        if not os.path.isfile(path):
            continue
        font_manager.fontManager.addfont(path)
        name = font_manager.FontProperties(fname=path).get_name()
        plt.rcParams["font.family"] = name
        plt.rcParams["axes.unicode_minus"] = False
        return


def style_like_live(ax: Any, metric: str, legend: str, *, zero_floor: bool | None = None) -> None:
    title, ylabel, zero = AXIS.get(metric, (metric, metric, True))
    if zero_floor is not None:
        zero = zero_floor
    ax.set_title(title)
    ax.set_xlabel(X_LABEL)
    ax.set_ylabel(ylabel)
    ax.set_xlim(left=0)
    if zero:
        ax.set_ylim(bottom=0)
    if legend:
        ax.legend()


def marker_chart_writer(
    markers: list[dict[str, Any]],
) -> Callable[[Path, list[float], list[float], str], None]:
    """matplotlib writer that overlays the same job-level markers on every chart."""

    def writer(path: Path, xs: list[float], ys: list[float], ylabel: str) -> None:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            return
        _ensure_cjk()
        fig, ax = plt.subplots()
        t0, rel = elapsed_xs(xs)
        ax.plot(rel, ys, label=legend_from_chart(path))
        style_like_live(ax, ylabel, legend_from_chart(path))
        annotate_chart(ax, rel, shift_markers(markers, t0))
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path)
        plt.close(fig)

    return writer


def _plot_net(run_dir: Path, *, net_plotter=None) -> list[Path]:
    if net_plotter is not None:
        return list(net_plotter(run_dir))
    try:
        from eth_monitor.plot import plot_run as eth_plot
    except ImportError:
        return []
    return list(eth_plot(run_dir, writer=marker_chart_writer(load_markers(run_dir))))


def metric_series(rows: list[dict[str, Any]], metric: str) -> tuple[list[Any], list[float]]:
    xs: list[Any] = []
    ys: list[float] = []
    for row in rows:
        if metric not in row or row[metric] is None:
            continue
        try:
            ys.append(float(row[metric]))
        except (TypeError, ValueError):
            continue
        xs.append(row["ts"])
    return xs, ys


def _default_plotter(jsonl_path: Path, charts_dir: Path) -> list[Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    _ensure_cjk()
    rows = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    if not rows:
        return []
    markers = load_markers(jsonl_path.parent.parent)
    out: list[Path] = []
    for metric in ("cpu_pct", "rss_mb", "io_read_bps", "io_write_bps"):
        metric_xs, metric_ys = metric_series(rows, metric)
        if not metric_ys:
            continue
        dest = charts_dir / f"{jsonl_path.stem}_{metric}.png"
        fig, ax = plt.subplots()
        t0, rel = elapsed_xs(metric_xs)
        label = legend_from_rows(rows)
        ax.plot(rel, metric_ys, label=label)
        style_like_live(ax, metric, label)
        annotate_chart(ax, rel, shift_markers(markers, t0))
        fig.savefig(dest)
        plt.close(fig)
        out.append(dest)
    return out
