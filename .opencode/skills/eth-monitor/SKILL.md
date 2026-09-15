---
name: eth-monitor
description: >-
  Interpret host ethernet rx/tx and optional per-PID TCP timeseries collected
  by the agent-sidecar overlap supervisor (eth_monitor.collect_loop). Use when
  series/{host}_net.jsonl, series/{host}_pid{pid}_net.jsonl, eth_rx_bps /
  eth_tx_bps, tcp_rx_bps / tcp_tx_bps, or ethernet/TCP PNG paths appear.
compatibility: opencode
---

# Host ethernet / PID TCP monitor (this sidecar)

This skill describes **agent-sidecar** collection, not `eth-monitor wrap`.

The overlap supervisor on each compute node runs `eth-monitor`, which calls
`eth_monitor.collect.collect_loop` until stop. Host ethernet JSONL is always
host + iface (not pid). When `collect_loop` is given `match` (same
`--match` / `--agent-match` as proc-monitor), the same loop also writes
per-PID TCP series. Do **not** treat either curve as MPI message rates.
Do **not** scrape `/proc/net` or open netlink from the model.

Do **not** confuse `{host}_pid{pid}_net.jsonl` (TCP bytes) with mpi-monitor
`{host}_pid{pid}.jsonl` (CPU/RSS/block IO).

## When to use

- Job-assist should explain ethernet from `series/{host}_net.jsonl` and eth PNG
- `telemetry.json` `summary` has `eth_rx_bps_peak` / `eth_tx_bps_peak`
- PID TCP paths appear: `series/{host}_pid{pid}_net.jsonl` or
  `charts/{host}_pid{pid}_tcp_{rx,tx}_bps.png`
- Live overlay shows ethernet rx/tx charts (humans only; text-only model)

**Not** for process CPU/RSS/block IO (`mpi-monitor` skill) or IB/verbs/UDP.

## Artifacts

```text
{run_dir}/
  series/{host}_net.jsonl
  series/{host}_pid{pid}_net.jsonl   # only when collect_loop match is set
  charts/{host}_{iface}_eth_rx_bps.png
  charts/{host}_{iface}_eth_tx_bps.png
  charts/{host}_pid{pid}_tcp_rx_bps.png
  charts/{host}_pid{pid}_tcp_tx_bps.png
  tcp_info_partial                   # kernel tcp_info too short (optional)
  events/eth_monitor_import.err      # collect import failed (optional)
```

Host JSONL: `ts`, `host`, `iface`, `eth_rx_bps`, `eth_tx_bps` (optional
`eth_rx_pps` / `eth_tx_pps`). Bond slaves, loopback, veth, and InfiniBand
names are excluded. First sample rates are 0.

Pid-net JSONL: `ts`, `host`, `pid`, `comm`, `tcp_rx_bps`, `tcp_tx_bps`.
Live TCP sockets at sample time only. See [reference.md](reference.md).

## How to interpret

1. Trust `summary.eth_*_peak` for NIC rates. Do not embed every JSONL line.
   Healthy ethernet jitter is not a chart marker and does not start live
   OpenCode. Marker overlays on eth/TCP PNGs come from job point events
   (`mpi_abort` / `mpi_segfault` / `slurm_oom` / `node_local`), not NIC rates.
2. Zero ethernet with busy CPU/IO often means MPI or Lustre ran on IB, not
   that the job was idle.
3. `tcp_*_bps` are kernel TCP payload-class counters. They are typically
   smaller than `eth_*_bps` (headers, other tenants, non-TCP). They are
   **not** NIC rates and **not** MPI bytes.
4. Missing pid-net files means match was omitted or no PID matched; that is
   not a job fault by itself. Do not invent ranks or TCP samples.
5. Short TCP connections, UDP, and IB/RDMA are not in pid-net. `tcp_info_partial`
   means tx used `bytes_acked` fallback — treat rates as approximate.
6. Healthy ethernet or TCP jitter is **not** a live OpenCode trigger.
7. Missing eth-monitor on PYTHONPATH writes `eth_monitor_import.err` (fail-soft).
8. Do **not** generate images or read PNG pixels. Name PNG paths from
   `evidence_paths` only.

## PYTHONPATH

- `AGENT_ETH_MONITOR_SRC` or `/shared/eth-monitor/src`

## Forbidden

- Calling ethernet or TCP rates MPI traffic
- Mixing pid-net JSONL with mpi-monitor CPU/RSS/IO JSONL
- Copying NIC `eth_*_bps` into a PID TCP story (or the reverse)
- `eth-monitor wrap` as the happy path for this product
- Triggering live OpenCode from NIC or TCP counters
- `scancel` / `scontrol`
