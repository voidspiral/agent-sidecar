## Why

The cluster demo binary `examples/mpi_io_load.c` stays in an NFS write+fsync
loop for its whole run. Live overlay then shows CPU at ~5% after a short
startup spike, which looks like a bad collector even though the job is
IO-wait bound. Operators need the same binary to enter a CPU-dense phase
after IO so CPU and IO charts both have a visible regime change.

## What Changes

- Extend `mpi_io_load` with a second phase: simulated CPU-dense work after
  the existing per-rank write/fsync/read loop.
- Keep argv compatible: `mpi_io_load [io_seconds] [work_dir]` still runs
  the IO phase first. Optional third argument sets CPU-phase seconds.
- Close and unlink the per-rank file before the CPU phase so the second
  phase does not keep generating write_bytes.
- Update README, demo script, and launch-fail example comments to describe
  both phases.

## Non-goals

- No ClusterHelm control-plane integration: do not reuse, adapt, or consume
  Master/Slave, `workflow_runner`, `partition_report`, `run-slave.sh`,
  submit/wait, or gateway preflight/exclusion policy.
- No change to mpi-monitor `/proc` fields (`read_bytes` / `write_bytes`).
- No change to live overlay, wrap telemetry, or job-assist prompts.
- No real application kernel (LINPACK, STREAM); CPU work is a tight local
  loop on the existing 1 MiB buffer.
- No MPI communication in the CPU phase beyond barriers at phase boundaries.

## Capabilities

### New Capabilities

- `mpi-io-load`: demo MPI binary phases, argv, and rank-0 phase logs.

### Modified Capabilities

- (none)

## Impact

- **Code:** `examples/mpi_io_load.c`, `examples/Makefile` unchanged aside
  from rebuild.
- **Docs:** README EN/ZH, `scripts/demo_job_assist_mpi.sh`, launch-fail skill
  corrected command still uses the same binary path.
- **Tests:** unittest that the source (and, when `mpicc` is present, a
  1s+1s run) has IO then CPU phases; no live `/proc`, no `scancel`.
