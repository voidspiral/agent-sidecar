## ADDED Requirements

### Requirement: MPI segfault runtime code
`mpi-scan` / wrap stderr classification SHALL detect documented segfault
patterns and emit `mpi_segfault` with a stderr evidence path. Patterns MUST
include at least: a fixture-style `rank <N> segfault` line, `Segmentation
fault`, `SIGSEGV`, and `signal 11` / `exited (on|with) signal 11` style
launcher phrases. Matching MUST remain orthogonal to `mpi_abort` (abort-only
strings MUST NOT produce `mpi_segfault`).

#### Scenario: Fixture segfault line
- **WHEN** tee'd stderr contains `rank 0 segfault (null deref)`
- **THEN** an event with reason code `mpi_segfault` is present

#### Scenario: Launcher SIGSEGV wording
- **WHEN** stderr contains `Segmentation fault` or `Signal 11` / `SIGSEGV`
  without `MPI_Abort`
- **THEN** classification yields `mpi_segfault`

#### Scenario: Abort remains abort
- **WHEN** stderr contains `rank 0 called MPI_Abort` and no segfault pattern
- **THEN** classification yields `mpi_abort`, not `mpi_segfault`
