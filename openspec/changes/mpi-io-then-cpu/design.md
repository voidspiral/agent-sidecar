## Context

`examples/mpi_io_load.c` is the NFS happy-path demo for `agent srun` on this
cluster. Each rank writes, fsyncs, and reads a 1 MiB file under `work_dir`.
mpi-monitor records `/proc/<pid>/io` `write_bytes` (storage) and process
CPU from `utime+stime`. During the IO loop the process is blocked in NFS
`fsync`, so overlay CPU sits near 5% after MPI startup. That is correct
accounting, but the demo cannot show a CPU-dense regime.

Constraints: keep the binary name `mpi_io_load` (supervisor `--match`);
Python 3.10+ unittest; no ClusterHelm; do not change collect fields.

## Goals / Non-Goals

**Goals:** After the existing IO loop, run a local CPU burn for a
configurable duration; close/unlink first; barrier; rank-0 logs; argv
backward compatible.

**Non-Goals:** Changing `read_bytes` vs `rchar`; MPI collectives in the
burn loop; a second example binary; live-plot or job-assist changes.

## Decisions

### 1. Same binary, third argv for CPU seconds

Keep `mpi_io_load [io_seconds] [work_dir] [cpu_seconds]`. Defaults: 60, `.`,
30. `cpu_seconds == 0` skips the CPU phase so short IO-only checks remain.
Do not insert `cpu_seconds` as argv2 (would break `work_dir`).

### 2. Close and unlink before CPU, then `MPI_Barrier`

The IO phase already closes and unlinks at the end. CPU work uses the
in-memory 1 MiB buffer only (volatile checksum / mutate) so `-O2` cannot
delete the loop and `write_bytes` stays flat. Barrier after unlink so every
rank starts the burn together.

### 3. CPU burn is a tight local loop, not MPI compute

No `MPI_Allreduce` in the inner loop (that would add wait time on a
2-node, 1-core test cluster). Rank 0 logs `cpu_phase start` / `cpu_phase
done` with durations. IO-phase progress (`ops % 32`) stays.

### 4. Tests: source contract always; compile-run when mpicc exists

Unittest parses `examples/mpi_io_load.c` for argv3, unlink-before-CPU, and
phase log strings. If `mpicc` and `mpirun`/`mpiexec` are on PATH, compile
to a temp dir and run `1s IO + 1s CPU` with `work_dir` in tmp, assert
stderr markers and exit 0. Cluster `salloc` is ops verification, not CI.

## Risks / Trade-offs

- Wall time of the usual `mpi_io_load 60 /shared/mpi-io` grows from 60s to
  ~90s. Acceptable for overlay demos; pass `0` as argv3 to keep 60s IO-only.
- CPU loop will show ~100% of one core, not multi-core scale-out. Matches
  this cluster's 1 vCPU compute nodes.

## Migration Plan

Rebuild the NFS binary (`make -C examples` or `mpicc` onto `/shared`).
Existing two-arg commands keep working and gain a 30s CPU tail. Demo script
MAY pass `AGENT_MPI_CPU_SECONDS` (default 30).
