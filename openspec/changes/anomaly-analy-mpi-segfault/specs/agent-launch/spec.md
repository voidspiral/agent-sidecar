## ADDED Requirements

### Requirement: Wrap and analy route mpi_segfault pack
When wrap or `agent analy` sees tool/rollup `reason_code=mpi_segfault`,
deterministic analysis MUST select pack `mpi_segfault` (not `generic` /
`stub`). The segfault demo script MUST document expected
`reason_code=mpi_segfault` and `pid_count>0` after a short busy window.

#### Scenario: Pack selection for mpi_segfault
- **WHEN** telemetry `reason_code` is `mpi_segfault`
- **THEN** `select_pack` / `run_analysis` uses pack name `mpi_segfault`

#### Scenario: Demo documents expectations
- **WHEN** an operator runs the MPI segfault demo script
- **THEN** the script states expected `mpi_segfault` and sampled
  `pid_count>0`
