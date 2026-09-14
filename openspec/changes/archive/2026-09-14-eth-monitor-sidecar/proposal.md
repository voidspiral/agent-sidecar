## Why

Host ethernet rx/tx timeseries now live in the independent `eth-monitor`
package. The sidecar still only samples process CPU/RSS/IO, so live charts and
`summarize_series` cannot show NIC rates, and globbing `*.jsonl` would count
`{host}_net.jsonl` as extra pids. This change wires the new collector into the
overlap supervisor, NFS deploy, live overlay, and wrap PNG without putting
`/proc/net` scrape in the sidecar body.

## What Changes

- Add an `eth-monitor` tool plugin that imports `eth_monitor.collect.collect_loop`.
- Include it in default skills. Import failure is fail-soft (`events/eth_monitor_import.err`).
- Deploy a third tree `/shared/eth-monitor` and extend PYTHONPATH with
  `AGENT_ETH_MONITOR_SRC`.
- Live overlay adds `eth_rx_bps` / `eth_tx_bps` charts; ingest does not require
  `pid` for net JSONL; process charts stay uncontaminated.
- Wrap PNG dispatches `*_net.jsonl` to `eth_monitor.plot`.
- `summarize_series` counts pids only from `*_pid*.jsonl` and adds eth peaks.
- Job-assist standing docs and a new `.opencode/skills/eth-monitor` skill.

## Non-goals

- ClusterHelm control-plane integration.
- InfiniBand, pcap, per-pid net, PMPI.
- Triggering live OpenCode from ethernet rate changes.
- Changing mpi-monitor's process collect contract.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `sidecar-spi`: sixth tool `eth-monitor`; fail-soft import; events stay empty
  for healthy NIC series.
- `live-overlay-charts`: two ethernet overlay charts; net ingest by host+iface.
- `job-telemetry`: `pid_count` ignores net JSONL; add `eth_rx_bps_peak` /
  `eth_tx_bps_peak`.
- `agent-launch`: deploy third tree and three-entry PYTHONPATH.

## Impact

- **Code:** plugin, deploy, `sidecar_pythonpath`, live plot HTML/ingest,
  wrap plotter, telemetry summary, docs/skills.
- **Deps:** neighbor package `eth-monitor` on compute-node PYTHONPATH (optional;
  missing is fail-soft).
- **Ops:** `agent deploy --mpi-monitor DIR --eth-monitor DIR`.
