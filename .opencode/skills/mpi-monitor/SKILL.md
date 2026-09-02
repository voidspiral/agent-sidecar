---
name: mpi-monitor
description: >-
  Interpret process CPU, RSS, and IO timeseries collected by the agent-sidecar
  overlap supervisor (mpi-monitor collect_loop). Use when the user or job-assist
  prompt mentions series JSONL, charts PNG, rank CPU/RSS/IO, or empty series.
compatibility: opencode
---

# MPI process monitor (this sidecar)

This skill describes **agent-sidecar** collection, not a gateway wrap CLI.

The overlap supervisor on each compute node runs `proc-monitor`, which calls
`mpi_monitor.collect.collect_loop` until SIGTERM. JSONL lands under the wrap
run directory. After wrap, the login host may write optional PNG charts.

Do **not** run `mpi-monitor wrap`. Do **not** SSH a collector. Matching is
`--match` (user binary basename, or `--agent-match`).

## When to use

- Job-assist should explain CPU / RSS / IO from `series/` and `charts/`
- `telemetry.json` `summary` has `cpu_*`, `rss_peak_mb`, IO fields, `pid_count`
- Series are empty (`host_count=0` / `pid_count=0`) and you need to say whether
  collect failed vs the job never started

**Not** for node RAM/swap/OOM (that is `node-diag`) or SLURM job state
(`slurm-tap`).

## Artifacts

```text
{run_dir}/
  telemetry.json
  series/{host}_pid{pid}.jsonl
  charts/{stem}_{cpu_pct|rss_mb|io_read_bps|io_write_bps}.png
  events/mpi_monitor_import.err    # collect import failed (optional)
```

JSONL fields: `ts`, `host`, `pid`, `cpu_pct`, `rss_mb`, `io_read_bps`,
`io_write_bps`, optional `rank`. See [reference.md](reference.md).

Launchers are never sampled: `srun`, `mpirun`, `mpiexec`, `orted`, `orterun`,
`prted`, `prterun`, `sshd`, `ssh`, `hydra_pmi_proxy`, collector PID.

## How to interpret

1. Trust `telemetry.json` `summary` and `reason_code`. Do not scrape `/proc`.
2. Name chart paths from `evidence_paths`. Do **not** generate images; models
   used here are text-only.
3. Empty series with user exit 0 and `reason_code=ok` may mean `--match` missed
   the binary or mpi-monitor was not on `PYTHONPATH` (`mpi_monitor_import`).
4. Empty series with `execution_error` and `pid_count=0` is a **start failure**
   — use the launch-fail skill, not an IO/CPU story.
5. Missing matplotlib: JSONL stays; PNG may be absent. That is not a job fault.

## PYTHONPATH

Sidecar processes need both trees:

- `agent-sidecar/src`
- `AGENT_MPI_MONITOR_SRC` or `/shared/mpi-monitor/src`

## Forbidden

- `mpi-monitor wrap` / gateway `--hosts` as the happy path for this product
- Inventing ranks or samples that are not in summary/series paths
- Sending PNG bytes to the model
- `scancel` / `scontrol`
- Overlaying multiple PIDs in one imagined chart (on-disk charts are per pid × metric)
