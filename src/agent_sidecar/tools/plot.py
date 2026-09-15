"""Optional PNG plots; JSONL remains if matplotlib is missing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agent_sidecar.chart_markers import load_markers, markers_in_range

MARKER_COLORS = {
    "mpi_abort": "#c0392b",
    "mpi_segfault": "#d35400",
    "slurm_oom": "#8e44ad",
    "node_local": "#f1c40f",
}


def plot_run(run_dir: Path, *, plotter=None, net_plotter=None) -> list[Path]:
    """Write charts if a plotter is available. Never delete JSONL."""
    series = run_dir / "series"
    pid_files = list(series.glob("*_pid*.jsonl")) if series.is_dir() else []
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
    visible = markers_in_range(markers, list(xs))
    if not visible:
        return
    _ymin, ymax = ax.get_ylim()
    for rec in visible:
        ts = float(rec["ts"])
        color = MARKER_COLORS.get(str(rec.get("reason_code") or ""), "#7f8c8d")
        ax.axvline(ts, color=color, linestyle="--", linewidth=0.9, zorder=3)
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
        fig, ax = plt.subplots()
        ax.plot(xs, ys)
        ax.set_xlabel("ts")
        ax.set_ylabel(ylabel)
        annotate_chart(ax, xs, markers)
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


def _default_plotter(jsonl_path: Path, charts_dir: Path) -> list[Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    rows = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    if not rows:
        return []
    xs = [r["ts"] for r in rows]
    markers = load_markers(jsonl_path.parent.parent)
    out: list[Path] = []
    for metric in ("cpu_pct", "rss_mb", "io_read_bps", "io_write_bps"):
        dest = charts_dir / f"{jsonl_path.stem}_{metric}.png"
        fig, ax = plt.subplots()
        ax.plot(xs, [r.get(metric, 0) for r in rows])
        annotate_chart(ax, xs, markers)
        fig.savefig(dest)
        plt.close(fig)
        out.append(dest)
    return out
