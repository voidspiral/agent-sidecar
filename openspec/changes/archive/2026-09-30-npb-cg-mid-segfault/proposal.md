## Why

Short busy-loop fixtures (`mpi_io_load`, `mpi_fault_segfault`) do not exercise a
~60s NAS Parallel Benchmark (NPB) communication workload. Operators need one
P4-style cluster demo: CG on two ranks, real inverse-power iterations, then a
mid-run segfault so sidecar charts and `mpi_segfault` analysis still apply.

## What Changes

- Add an NPB CG Class B example that is built from an operator-supplied
  `NPB_MPI_ROOT` (no vendored NPB tree, no hardcoded user home).
- Patch CG’s main iteration loop so rank 0 null-derefs at the midpoint
  iteration and prints `rank 0 segfault (null deref)` to stderr first.
- Add a submit-host demo script that compiles on the login/shared path and
  launches with `sidecar.sh srun -N2 -n2` (not WSL-as-cluster).
- Keep existing `mpi_fault_segfault` fixture unchanged.

## Capabilities

### New Capabilities

- `npb-cg-mid-segfault-example`: NPB CG Class B ~60s two-rank example with a
  mid-iteration rank-0 segfault, built from `NPB_MPI_ROOT` and launched via
  sidecar on the cluster.

### Modified Capabilities

- (none)

## Non-goals

- ClusterHelm control-plane integration (Master/Slave, workflow_runner,
  partition_report, submit/wait, preflight).
- Other NPB kernels (EP/MG/FT/IS/LU/BT/SP/BT-IO/DT), Class C+ sizes, or
  BT/SP square-process constraints.
- Changing `reason_code` classification or analysis packs (reuse
  `mpi_segfault`).
- Running NPB inside WSL as a substitute for mn/`cn*` results.
- Vendoring the NAS NPB source tree into this repository.

## Impact

- `examples/npb_cg_mid_segfault/` (patch + build helper)
- `scripts/demo_npb_cg_segfault.sh`
- `examples/Makefile` / `.gitignore` for the produced binary
- Tests that the patch applies to NPB 3.4.3 `CG/cg.f90` and injects the
  required stderr line and midpoint guard
- No change to sidecar Python classify/pack modules unless tests need a
  documented match string (already covered by `rank N segfault`)
