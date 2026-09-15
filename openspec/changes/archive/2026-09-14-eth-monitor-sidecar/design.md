## Context

See `proposal.md`. Neighbor package `eth-monitor` already provides
`collect_loop` and plot. This sidecar currently imports only mpi-monitor,
globs all `*.jsonl` as pids, and live ingest drops samples without `pid`.
TDD with unittest (failing tests first). No ClusterHelm. No hardcoded homes.

## Goals / Non-Goals

**Goals:**

- Thin `eth-monitor` plugin mirroring `ProcMonitor`.
- Three-tree deploy and PYTHONPATH.
- Live two ethernet charts; wrap PNG dispatch; summary peaks; pid_count fix.
- Job-assist skill + standing-doc sync.

**Non-Goals:**

- IB, pcap, live OpenCode on ethernet jitter, editing mpi-monitor.

## Decisions

### 1. Implementation method: TDD

Failing tests first for plugin import-error, default skills, deploy plan,
live ingest of net JSONL, pid_count, plot skip of net files as CPU charts.

### 2. Plugin shape

`EthMonitor` in `src/agent_sidecar/tools/eth_monitor.py` imports
`eth_monitor.collect.collect_loop` (injected in tests). Thread +
`.collect-stop-eth-{host}`. Stop writes the file. Artifacts are `*_net.jsonl`.
Events always `[]`.

**Alternatives:** scrape `/proc/net` in sidecar (rejected).

### 3. PYTHONPATH

`sidecar_pythonpath` = `{src}:{mpi}:{eth}` with
`AGENT_ETH_MONITOR_SRC` default `/shared/eth-monitor/src`.
`agent deploy` requires `--eth-monitor` (or second positional after mpi).

### 4. Live ingest split

Glob `*_pid*.jsonl` vs `*_net.jsonl`. Shared `t0`. Ethernet visible cap
by rx peak. HTML six canvases.

### 5. Plot dispatch

`tools/plot.py` routes `*_net.jsonl` to `eth_monitor.plot.plot_run` (or
injected plotter); remaining files keep the four process metrics.

## Risks / Trade-offs

- [NFS MPI on IB shows flat eth] → skill/docs say not MPI traffic.
- [Deploy CLI now requires eth-monitor] → **BREAKING** for old
  `deploy_shared.sh <mpi-dir>` one-arg form; add required second tree.

## Migration Plan

Operators pass `--eth-monitor` on deploy. Missing package is fail-soft at
job time. Update README examples.

## Open Questions

None.
