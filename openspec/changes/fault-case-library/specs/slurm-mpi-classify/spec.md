# Delta: MPI FPE / deadlock codes

## ADDED Requirements

### Requirement: MPI runtime codes
`mpi-scan` SHALL detect documented patterns in captured stdout/stderr including `MPI_Abort`, PMIx abort, disconnected rank, Hydra `assert (!closed)`, segmentation faults, floating-point exceptions, and fixture deadlock markers, and MUST emit `mpi_abort`, `mpi_segfault`, `mpi_fpe`, `mpi_deadlock`, or a more specific documented code with a stderr tail path.

#### Scenario: SIGFPE in stderr
- **WHEN** tee'd output contains `Floating point exception`, `SIGFPE`, `signal 8`, or `rank N fpe`
- **THEN** an event with reason code `mpi_fpe` is present

#### Scenario: Deadlock fixture marker in stderr
- **WHEN** tee'd output contains `rank N deadlock`
- **THEN** an event with reason code `mpi_deadlock` is present
