## Purpose

Cluster demo MPI binary that first generates per-rank NFS write/fsync/read
load, then a local CPU-dense phase, so live process charts show two regimes.

## ADDED Requirements

### Requirement: IO phase then CPU phase
`examples/mpi_io_load` SHALL run an IO-dense phase first, then a simulated
CPU-dense phase. The CPU phase MUST NOT keep the per-rank scratch file open.
Ranks MUST `MPI_Barrier` at the IO-to-CPU boundary so they enter the CPU
phase together.

#### Scenario: Default two-phase run
- **WHEN** the binary is started with no extra duration flags beyond the
  existing `io_seconds` and `work_dir`
- **THEN** it completes the write/fsync/read loop for the IO duration, closes
  and unlinks the per-rank file, then burns CPU for the default CPU duration

#### Scenario: CPU phase emits no further file IO
- **WHEN** the CPU phase is running
- **THEN** the process MUST NOT write or fsync the per-rank scratch file

### Requirement: Optional CPU duration argv
The command line SHALL remain `mpi_io_load [io_seconds] [work_dir]` with an
optional third argument `cpu_seconds`. Omitted `cpu_seconds` defaults to 30.
`cpu_seconds` of 0 MUST skip the CPU phase. Invalid or empty `io_seconds`
MUST keep the existing default of 60.

#### Scenario: Third argument sets CPU seconds
- **WHEN** argv is `mpi_io_load 20 /shared/mpi-io 10`
- **THEN** the IO phase lasts 20 seconds and the CPU phase lasts 10 seconds

#### Scenario: Zero skips CPU phase
- **WHEN** argv is `mpi_io_load 5 /tmp 0`
- **THEN** after the IO phase the process finalizes without a CPU burn loop

### Requirement: Rank-0 phase logs
Rank 0 SHALL log IO-phase completion and CPU-phase start/end on stderr so
operators can align overlay charts with phase boundaries. Other ranks MUST
NOT spam the same progress lines.

#### Scenario: Rank 0 prints phase markers
- **WHEN** both phases run to completion
- **THEN** rank-0 stderr includes an IO-done line and a CPU-done line
