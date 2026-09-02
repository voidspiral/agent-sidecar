# MPI monitor — JSON / paths (agent-sidecar)

Standalone neighbor package `mpi-monitor`. This sidecar imports
`mpi_monitor.collect.collect_loop` inside the overlap supervisor.

## JSONL sample line

```json
{
  "ts": 1787623567.7478287,
  "host": "cn1",
  "pid": 59020,
  "cpu_pct": 98.4,
  "rss_mb": 15.91,
  "io_read_bps": 0.0,
  "io_write_bps": 4096.0,
  "rank": 0
}
```

| Field | Type | Source |
|-------|------|--------|
| `ts` | float | Unix epoch seconds |
| `host` | string | short hostname |
| `pid` | int | matched task PID |
| `cpu_pct` | float | `/proc/<pid>/stat` utime+stime vs wall |
| `rss_mb` | float | `VmRSS` |
| `io_read_bps` / `io_write_bps` | float | `/proc/<pid>/io` deltas |
| `rank` | int (optional) | `PMIX_RANK` / `OMPI_COMM_WORLD_RANK` / `PMI_RANK` |

## Discovery (`--match`)

Match is a substring of **comm or argv0** (shebang: argv1 when argv0 is an
interpreter). A token that appears only in later argv is ignored.

## Paths in this sidecar

| Artifact | Path |
|----------|------|
| Run root | `{--agent-output-dir}/{run_id}/` |
| Telemetry | `{run_dir}/telemetry.json` |
| Series | `{run_dir}/series/{host}_pid{pid}.jsonl` |
| Charts | `{run_dir}/charts/{stem}_{cpu_pct\|rss_mb\|io_read_bps\|io_write_bps}.png` |

One PNG per process × metric when matplotlib is present. Missing matplotlib:
skip PNG, keep JSONL, do not fail wrap.

`--interval` default is `1.0` seconds (`--agent-interval` to override).
