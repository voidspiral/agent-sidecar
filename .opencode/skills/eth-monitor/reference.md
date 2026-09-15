# Ethernet / PID TCP — JSON / paths (agent-sidecar)

Standalone neighbor package `eth-monitor`. This sidecar imports
`eth_monitor.collect.collect_loop` inside the overlap supervisor.

## Host ethernet JSONL (`{host}_net.jsonl`)

```json
{
  "ts": 1787623567.7478287,
  "host": "cn1",
  "iface": "eth0",
  "eth_rx_bps": 1258291.0,
  "eth_tx_bps": 4096.0
}
```

| Field | Type | Source |
|-------|------|--------|
| `ts` | float | Unix epoch seconds |
| `host` | string | short hostname |
| `iface` | string | selected up ethernet or bond master |
| `eth_rx_bps` / `eth_tx_bps` | float | `/proc/net/dev` byte deltas / elapsed |
| `eth_rx_pps` / `eth_tx_pps` | float (optional) | packet deltas; plots use bps |

First sample per iface is `0.0`. Excluded names include loopback, `ib*`,
`mlx*`, `veth*`, docker/virbr/tun/tap/dummy, and bond slaves.

Plot host files matching `{host}_net.jsonl` **without** `_pid` in the name.

## PID TCP JSONL (`{host}_pid{pid}_net.jsonl`)

Present only when `collect_loop(..., match=...)` is set. Match is a
case-sensitive substring of `/proc/<pid>/comm` (same `--match` /
`--agent-match` idea as proc-monitor; not a wrap process tree).

```json
{
  "ts": 1787623567.7478287,
  "host": "cn1",
  "pid": 59020,
  "comm": "app",
  "tcp_rx_bps": 8192.0,
  "tcp_tx_bps": 1024.0
}
```

| Field | Type | Source |
|-------|------|--------|
| `ts` | float | Unix epoch seconds (same tick as host sample) |
| `host` | string | short hostname |
| `pid` | int | matched task PID |
| `comm` | string | `/proc/<pid>/comm` |
| `tcp_rx_bps` / `tcp_tx_bps` | float | sock_diag `tcp_info` byte deltas / elapsed |

Join is inode via `/proc/<pid>/fd` `socket:[inode]` plus
`NETLINK_SOCK_DIAG` (`AF_INET` / `AF_INET6` TCP). Tx prefers
`tcpi_bytes_sent`; short kernel struct falls back to `tcpi_bytes_acked`
and may write `{run_dir}/tcp_info_partial`. First sample per PID is `0.0`.

Not counted: UDP, InfiniBand/RDMA, sockets that closed between samples.

## Paths in this sidecar

| Artifact | Path |
|----------|------|
| Run root | `{--agent-output-dir}/{run_id}/` |
| Host series | `{run_dir}/series/{host}_net.jsonl` |
| PID TCP series | `{run_dir}/series/{host}_pid{pid}_net.jsonl` |
| Host charts | `{run_dir}/charts/{host}_{iface}_eth_{rx\|tx}_bps.png` |
| PID TCP charts | `{run_dir}/charts/{host}_pid{pid}_tcp_{rx\|tx}_bps.png` |

Do not read mpi-monitor `{host}_pid{pid}.jsonl` as ethernet. Do not read
pid-net files as host NIC series. Missing matplotlib: skip PNG, keep JSONL.

`--interval` default is `1.0` seconds (`--agent-interval` to override).
