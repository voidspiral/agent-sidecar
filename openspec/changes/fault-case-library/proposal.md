# Change: fault-case-library

Add application/scheduler fault fixtures (调研2 IDs), `mpi_fpe` / `mpi_deadlock` reason codes, and telemetry assertion scripts. Hardware dirs `examples/18`–`23` stay empty.

## Why
Cluster demos for SIGFPE and MPI deadlock were rolled up as `slurm_failed` / `timeout` because `anomalies_from_artifacts` follows `events/` filename order. A fixed rollup priority lets scripts assert the MPI-specific codes.

## Specs
- `slurm-mpi-classify`: `mpi_fpe`, `mpi_deadlock` patterns
- `job-telemetry`: rollup prefers MPI codes over `timeout` / `slurm_failed`
