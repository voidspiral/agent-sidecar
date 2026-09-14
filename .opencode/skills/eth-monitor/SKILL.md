---
name: eth-monitor
description: >-
  Interpret host ethernet rx/tx timeseries collected by the agent-sidecar
  overlap supervisor (eth_monitor.collect_loop). Use when series/{host}_net.jsonl,
  eth_rx_bps / eth_tx_bps, or ethernet PNG paths appear.
compatibility: opencode
---

# Host ethernet monitor (this sidecar)

This skill describes **agent-sidecar** collection, not `eth-monitor wrap`.

The overlap supervisor on each compute node runs `eth-monitor`, which calls
`eth_monitor.collect.collect_loop` until stop. JSONL is host + iface, not pid.
Do **not** treat these curves as MPI message rates. Do **not** scrape `/proc/net`.

## When to use

- Job-assist should explain ethernet from `series/{host}_net.jsonl` and eth PNG
- `telemetry.json` `summary` has `eth_rx_bps_peak` / `eth_tx_bps_peak`
- Live overlay shows ethernet rx/tx charts (humans only; text-only model)

**Not** for process CPU/RSS/block IO (`mpi-monitor` skill) or IB/verbs.

## Artifacts

```text
{run_dir}/
  series/{host}_net.jsonl
  charts/{host}_{iface}_eth_rx_bps.png
  charts/{host}_{iface}_eth_tx_bps.png
  events/eth_monitor_import.err    # collect import failed (optional)
```

JSONL fields: `ts`, `host`, `iface`, `eth_rx_bps`, `eth_tx_bps`. Bond slaves,
loopback, and InfiniBand names are excluded. First sample rates are 0.

## How to interpret

1. Trust `summary.eth_*_peak`. Do not embed every JSONL line.
2. Zero ethernet with busy CPU/IO often means MPI or Lustre ran on IB, not
   that the job was idle.
3. Healthy ethernet jitter is **not** a live OpenCode trigger.
4. Missing eth-monitor on PYTHONPATH writes `eth_monitor_import.err` (fail-soft).
5. Do **not** generate images.

## PYTHONPATH

- `AGENT_ETH_MONITOR_SRC` or `/shared/eth-monitor/src`

## Forbidden

- Calling ethernet rates MPI traffic
- `eth-monitor wrap` as the happy path for this product
- Triggering live OpenCode from NIC counters
- `scancel` / `scontrol`
