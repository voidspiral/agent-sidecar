"""Optional PNG plots; JSONL remains if matplotlib is missing."""

from __future__ import annotations

import json
from pathlib import Path


def plot_run(run_dir: Path, *, plotter=None) -> list[Path]:
    """Write charts if a plotter is available. Never delete JSONL."""
    series = run_dir / "series"
    jsonl = list(series.glob("*.jsonl")) if series.is_dir() else []
    if plotter is None:
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            return []
        plotter = _default_plotter
    charts = run_dir / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for path in jsonl:
        written.extend(plotter(path, charts))
    return written


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
    out: list[Path] = []
    for metric in ("cpu_pct", "rss_mb", "io_read_bps", "io_write_bps"):
        dest = charts_dir / f"{jsonl_path.stem}_{metric}.png"
        fig, ax = plt.subplots()
        ax.plot(xs, [r.get(metric, 0) for r in rows])
        fig.savefig(dest)
        plt.close(fig)
        out.append(dest)
    return out
