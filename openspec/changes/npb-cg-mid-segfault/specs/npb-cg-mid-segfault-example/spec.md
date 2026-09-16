## Purpose

Provides a ~60s two-rank NPB CG Class B sidecar demo that faults with a rank-0
segfault at the midpoint iteration so live charts and `mpi_segfault` analysis
see a real communication kernel rather than a short busy loop.

## ADDED Requirements

### Requirement: Mid-iteration CG segfault fixture
The repository SHALL provide an NPB CG Class B example built from operator
`NPB_MPI_ROOT` (NPB 3.4-MPI tree). Rank 0 MUST print
`rank 0 segfault (null deref)` to stderr and then null-dereference once the
CG timed region reaches 30 seconds (half of the ~60s target). Other ranks
MUST exit without `MPI_Finalize` so the job does not hang. The example MUST
NOT hardcode a user home path.

#### Scenario: Patch injects midpoint rank-0 crash
- **WHEN** the CG patch is applied to NPB 3.4.3 `CG/cg.f90`
- **THEN** the patched source records `crash_t0 = mpi_wtime()` after
  `timer_start(1)` and guards on `mpi_wtime() - crash_t0 >= 30` seconds
  (NPB 3.4 `timer_read` stays 0 until `timer_stop`), rank 0
  writes `rank 0 segfault (null deref)` to stderr and null-dereferences, and
  other ranks sleep then `_exit`

#### Scenario: Build uses NPB_MPI_ROOT
- **WHEN** `NPB_MPI_ROOT` is unset or not an NPB 3.4-MPI tree
- **THEN** the build helper exits non-zero and prints that `NPB_MPI_ROOT`
  must point at the NPB 3.4-MPI directory

### Requirement: Cluster demo launch
The demo script SHALL compile and run on the submit/login host against shared
storage using `sidecar.sh srun` with two nodes and two ranks (`-N2 -n2` or
equivalent). It MUST pass `--agent-match` matching the CG binary basename.
It MUST NOT treat WSL as the cluster.

#### Scenario: Demo documents two-rank CG
- **WHEN** an operator reads or runs `scripts/demo_npb_cg_segfault.sh`
- **THEN** the script builds the patched CG Class B binary onto a shared
  path and launches it with sidecar `srun` on two ranks, expecting
  `reason_code=mpi_segfault` after the mid-run crash
