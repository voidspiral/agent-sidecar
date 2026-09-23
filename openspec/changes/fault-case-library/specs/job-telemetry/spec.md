# Delta: rollup priority

## ADDED Requirements

### Requirement: reason_code rollup prefers MPI-specific codes
`rollup_reason_code` SHALL pick a primary `reason_code` by a fixed priority list, not by `events/` filename order. MPI-specific codes (`mpi_abort`, `mpi_segfault`, `mpi_fpe`, `mpi_deadlock`) MUST outrank `timeout` and `slurm_failed`. `slurm_oom`, `node_local`, and `node_fail` MUST still outrank generic `execution_error`.

#### Scenario: Deadlock marker plus SLURM TIMEOUT
- **WHEN** `events/stderr.tail` contains `rank N deadlock` and `events/slurm.json` reports TIMEOUT
- **THEN** `JobTelemetry.reason_code` is `mpi_deadlock`

#### Scenario: SIGFPE plus SLURM FAILED
- **WHEN** stderr classifies as `mpi_fpe` and accounting reports FAILED
- **THEN** `JobTelemetry.reason_code` is `mpi_fpe`
