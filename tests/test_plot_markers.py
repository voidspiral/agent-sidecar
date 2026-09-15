"""Wrap PNG overlay uses axvline for in-range chart markers."""

from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from pathlib import Path as _Path
from unittest import mock

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

from agent_sidecar.chart_markers import record_marker
from agent_sidecar.telemetry import ensure_run_layout
from agent_sidecar.tools.plot import annotate_chart, marker_chart_writer, plot_run


def _pid_line(ts: float) -> str:
    return (
        json.dumps(
            {
                "ts": ts,
                "host": "h1",
                "pid": 1,
                "cpu_pct": 1.0,
                "rss_mb": 2.0,
                "io_read_bps": 0,
                "io_write_bps": 0,
            }
        )
        + "\n"
    )


class TestPlotMarkers(unittest.TestCase):
    def test_annotate_chart_skips_out_of_range(self) -> None:
        ax = mock.Mock()
        ax.get_ylim.return_value = (0.0, 10.0)
        markers = [
            {
                "ts": 2.0,
                "reason_code": "mpi_abort",
                "host": "submit",
                "evidence_path": "events/stderr.tail",
            },
            {
                "ts": 99.0,
                "reason_code": "slurm_oom",
                "host": "cn1",
                "evidence_path": "events/slurm.json",
            },
        ]
        annotate_chart(ax, [1.0, 3.0], markers)
        xs = [call.args[0] for call in ax.axvline.call_args_list]
        self.assertEqual(xs, [2.0])
        labels = [call.args[2] for call in ax.text.call_args_list]
        self.assertEqual(labels, ["submit mpi_abort"])
        ax.set_xlim.assert_called_once_with(1.0, 3.0)

    def test_annotate_chart_keeps_abort_just_after_last_sample(self) -> None:
        ax = mock.Mock()
        ax.get_ylim.return_value = (0.0, 10.0)
        markers = [
            {
                "ts": 15.08,
                "reason_code": "mpi_abort",
                "host": "submit",
                "evidence_path": "events/stderr.tail",
            }
        ]
        annotate_chart(ax, [1.0, 14.24], markers)
        xs = [call.args[0] for call in ax.axvline.call_args_list]
        self.assertEqual(xs, [15.08])
        ax.set_xlim.assert_called_once_with(1.0, 15.08)

    def test_process_png_calls_axvline_for_in_range_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = ensure_run_layout(Path(tmp))
            (run_dir / "series" / "h1_pid1.jsonl").write_text(
                _pid_line(1.0) + _pid_line(3.0), encoding="utf-8"
            )
            record_marker(
                run_dir,
                reason_code="mpi_abort",
                host="submit",
                evidence_path="events/stderr.tail",
                ts=2.0,
            )
            record_marker(
                run_dir,
                reason_code="node_local",
                host="cn1",
                evidence_path="events/node-diag.txt",
                ts=50.0,
            )
            fake_ax = mock.Mock()
            fake_fig = mock.Mock()
            fake_ax.get_ylim.return_value = (0.0, 10.0)
            with mock.patch("matplotlib.pyplot.subplots", return_value=(fake_fig, fake_ax)):
                with mock.patch("matplotlib.pyplot.close"):
                    with mock.patch("matplotlib.pyplot.savefig"):
                        written = plot_run(run_dir, net_plotter=lambda _r: [])
            self.assertEqual(len(written), 4)
            xs = [call.args[0] for call in fake_ax.axvline.call_args_list]
            self.assertEqual(xs, [2.0, 2.0, 2.0, 2.0])
            self.assertNotIn(50.0, xs)

    def test_eth_writer_injection_draws_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = ensure_run_layout(Path(tmp))
            (run_dir / "series" / "h1_net.jsonl").write_text(
                json.dumps(
                    {
                        "ts": 1.0,
                        "host": "h1",
                        "iface": "eth0",
                        "eth_rx_bps": 1.0,
                        "eth_tx_bps": 2.0,
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "ts": 3.0,
                        "host": "h1",
                        "iface": "eth0",
                        "eth_rx_bps": 3.0,
                        "eth_tx_bps": 4.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            record_marker(
                run_dir,
                reason_code="mpi_segfault",
                host="submit",
                evidence_path="events/stderr.tail",
                ts=2.0,
            )
            captured: dict[str, object] = {}

            def fake_eth(run_dir_arg, *, writer=None, **_kw):
                captured["writer"] = writer
                dest = run_dir_arg / "charts" / "h1_eth0_eth_rx_bps.png"
                writer(dest, [1.0, 3.0], [1.0, 3.0], "eth rx")
                return [dest]

            fake_ax = mock.Mock()
            fake_fig = mock.Mock()
            fake_ax.get_ylim.return_value = (0.0, 5.0)
            eth_pkg = types.ModuleType("eth_monitor")
            eth_plot = types.ModuleType("eth_monitor.plot")
            eth_plot.plot_run = fake_eth
            fake_ax_ctx = mock.patch("matplotlib.pyplot.subplots", return_value=(fake_fig, fake_ax))
            close_ctx = mock.patch("matplotlib.pyplot.close")
            with mock.patch.dict(sys.modules, {"eth_monitor": eth_pkg, "eth_monitor.plot": eth_plot}):
                with fake_ax_ctx, close_ctx:
                    plot_run(run_dir, plotter=lambda *_a, **_k: [])
            self.assertTrue(callable(captured.get("writer")))
            xs = [call.args[0] for call in fake_ax.axvline.call_args_list]
            self.assertEqual(xs, [2.0])

    def test_no_markers_skips_axvline(self) -> None:
        ax = mock.Mock()
        ax.get_ylim.return_value = (0.0, 1.0)
        annotate_chart(ax, [1.0, 2.0], [])
        ax.axvline.assert_not_called()

    def test_marker_writer_is_callable(self) -> None:
        writer = marker_chart_writer([])
        self.assertTrue(callable(writer))
