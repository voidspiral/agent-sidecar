"""Tail series JSONL on the submit host into overlay snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_sidecar.chart_markers import CHART_MARKER_CODES

PROCESS_METRICS = ("cpu_pct", "rss_mb", "io_read_bps", "io_write_bps")
ETH_METRICS = ("eth_rx_bps", "eth_tx_bps")
METRICS = PROCESS_METRICS
MAX_POINTS = 900
VISIBLE_CAP = 48


def series_label(host: str, pid: int, rank: int | None) -> str:
    if rank is not None:
        return f"{host} r{rank}"
    return f"{host} pid {pid}"


def eth_label(host: str, iface: str) -> str:
    return f"{host} {iface}"


class LivePlotIngest:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        self._offset: dict[str, int] = {}
        self._rows: dict[tuple[str, int], dict[str, Any]] = {}
        self._eth_rows: dict[tuple[str, str], dict[str, Any]] = {}
        self._t0: float | None = None
        self._markers: list[dict[str, Any]] = []

    def poll(self) -> dict[str, Any]:
        series = self.run_dir / "series"
        if series.is_dir():
            for path in sorted(series.glob("*_pid*.jsonl")):
                self._ingest_file(path, kind="pid")
            for path in sorted(series.glob("*_net.jsonl")):
                self._ingest_file(path, kind="net")
        events = self.run_dir / "events"
        if events.is_dir():
            for path in sorted(events.glob("*_markers.jsonl")):
                self._ingest_file(path, kind="marker")
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        t0 = self._t0 if self._t0 is not None else 0.0
        grouped: dict[str, list[dict[str, Any]]] = {
            metric: [] for metric in PROCESS_METRICS + ETH_METRICS
        }
        peaks = {
            key: max((pt[1] for pt in rec["cpu"]), default=0.0)
            for key, rec in self._rows.items()
        }
        ranked = sorted(peaks.items(), key=lambda item: item[1], reverse=True)
        visible_keys = {key for key, _peak in ranked[:VISIBLE_CAP]}
        for key, rec in sorted(
            self._rows.items(), key=lambda item: (item[1]["host"], item[1]["pid"])
        ):
            host = rec["host"]
            pid = rec["pid"]
            rank = rec["rank"]
            label = series_label(host, pid, rank)
            cpu_peak = peaks.get(key, 0.0)
            payload = {
                "id": label,
                "label": label,
                "host": host,
                "pid": pid,
                "rank": rank,
                "visible": key in visible_keys,
                "cpu_peak": cpu_peak,
            }
            stores = {
                "cpu_pct": rec["cpu"],
                "rss_mb": rec["rss"],
                "io_read_bps": rec["io_r"],
                "io_write_bps": rec["io_w"],
            }
            for metric, store in stores.items():
                row = dict(payload)
                row["points"] = [[round(ts - t0, 6), val] for ts, val in store]
                grouped[metric].append(row)

        eth_peaks = {
            key: max((pt[1] for pt in rec["rx"]), default=0.0)
            for key, rec in self._eth_rows.items()
        }
        eth_ranked = sorted(eth_peaks.items(), key=lambda item: item[1], reverse=True)
        eth_visible = {key for key, _peak in eth_ranked[:VISIBLE_CAP]}
        for key, rec in sorted(
            self._eth_rows.items(), key=lambda item: (item[1]["host"], item[1]["iface"])
        ):
            host = rec["host"]
            iface = rec["iface"]
            label = eth_label(host, iface)
            payload = {
                "id": label,
                "label": label,
                "host": host,
                "iface": iface,
                "visible": key in eth_visible,
                "eth_rx_peak": eth_peaks.get(key, 0.0),
            }
            stores = {"eth_rx_bps": rec["rx"], "eth_tx_bps": rec["tx"]}
            for metric, store in stores.items():
                row = dict(payload)
                row["points"] = [[round(ts - t0, 6), val] for ts, val in store]
                grouped[metric].append(row)
        markers = []
        for rec in self._markers:
            markers.append(
                {
                    "reason_code": rec["reason_code"],
                    "host": rec["host"],
                    "ts": rec["ts"],
                    "x": round(float(rec["ts"]) - t0, 6),
                    "evidence_path": rec.get("evidence_path") or "",
                }
            )
        return {"t0": t0, "visible_cap": VISIBLE_CAP, "metrics": grouped, "markers": markers}

    def _ingest_file(self, path: Path, *, kind: str) -> None:
        key = str(path)
        offset = self._offset.get(key, 0)
        with path.open("rb") as fh:
            fh.seek(offset)
            chunk = fh.read()
        if not chunk:
            return
        split_at = chunk.rfind(b"\n")
        if split_at < 0:
            return
        consumed = chunk[: split_at + 1]
        self._offset[key] = offset + len(consumed)
        text = consumed.decode("utf-8", errors="replace")
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if kind == "net":
                self._add_eth_sample(rec)
            elif kind == "marker":
                self._add_marker(rec)
            else:
                self._add_sample(rec)

    def _add_sample(self, rec: dict[str, Any]) -> None:
        try:
            ts = float(rec["ts"])
            host = str(rec.get("host") or "")
            pid = int(rec["pid"])
        except (KeyError, TypeError, ValueError):
            return
        if self._t0 is None:
            self._t0 = ts
        rank_raw = rec.get("rank")
        rank = int(rank_raw) if rank_raw is not None else None
        slot = self._rows.setdefault(
            (host, pid),
            {
                "host": host,
                "pid": pid,
                "rank": rank,
                "cpu": [],
                "rss": [],
                "io_r": [],
                "io_w": [],
            },
        )
        if rank is not None:
            slot["rank"] = rank
        slot["cpu"].append([ts, float(rec.get("cpu_pct") or 0.0)])
        slot["rss"].append([ts, float(rec.get("rss_mb") or 0.0)])
        slot["io_r"].append([ts, float(rec.get("io_read_bps") or 0.0)])
        slot["io_w"].append([ts, float(rec.get("io_write_bps") or 0.0)])
        for name in ("cpu", "rss", "io_r", "io_w"):
            if len(slot[name]) > MAX_POINTS:
                slot[name] = slot[name][-MAX_POINTS:]

    def _add_eth_sample(self, rec: dict[str, Any]) -> None:
        try:
            ts = float(rec["ts"])
            host = str(rec.get("host") or "")
            iface = str(rec.get("iface") or "")
        except (KeyError, TypeError, ValueError):
            return
        if not iface:
            return
        if self._t0 is None:
            self._t0 = ts
        slot = self._eth_rows.setdefault(
            (host, iface),
            {"host": host, "iface": iface, "rx": [], "tx": []},
        )
        slot["rx"].append([ts, float(rec.get("eth_rx_bps") or 0.0)])
        slot["tx"].append([ts, float(rec.get("eth_tx_bps") or 0.0)])
        for name in ("rx", "tx"):
            if len(slot[name]) > MAX_POINTS:
                slot[name] = slot[name][-MAX_POINTS:]

    def _add_marker(self, rec: dict[str, Any]) -> None:
        code = str(rec.get("reason_code") or "")
        if code not in CHART_MARKER_CODES:
            return
        try:
            ts = float(rec["ts"])
        except (KeyError, TypeError, ValueError):
            return
        host = str(rec.get("host") or "")
        evidence = str(rec.get("evidence_path") or "")
        key = (code, evidence, host)
        if any(
            (m["reason_code"], m.get("evidence_path") or "", m["host"]) == key
            for m in self._markers
        ):
            return
        self._markers.append(
            {
                "ts": ts,
                "reason_code": code,
                "host": host,
                "evidence_path": evidence,
            }
        )
