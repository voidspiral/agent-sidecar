## 1. Tests first

- [x] 1.1 Add failing unittest that applies the CG patch to a stored NPB 3.4.3 iteration-loop snippet (and to `NPB_MPI_ROOT/CG/cg.f90` when present) and asserts 30s `timer_read` guard, rank 0 stderr line, null deref, and survivor `sleep`/`c_exit`
- [x] 1.2 Add failing unittest that `examples/npb_cg_mid_segfault/build.sh` exits non-zero with `NPB_MPI_ROOT` guidance when the env var is missing or not an NPB tree

## 2. Example and demo

- [x] 2.1 Add `examples/npb_cg_mid_segfault/cg.f90.patch` for NPB 3.4.3 and verify task 1.1 passes
- [x] 2.2 Implement `examples/npb_cg_mid_segfault/build.sh` (copy tree, patch, `make cg CLASS=${NPB_CG_CLASS:-B}`, install binary under `examples/`) and verify task 1.2 plus a dry run with a fake tree that only needs patch apply
- [x] 2.3 Add `scripts/demo_npb_cg_segfault.sh` using `sidecar.sh srun -N2 -n2`, `--agent-match` on the installed basename, shared output dir; gitignore the binary; no user-home hardcoding
- [x] 2.4 Out of phase 1: SPANK, automatic remediate, ClusterHelm adapter (do not implement)

## 3. Cluster check

- [ ] 3.1 On mn (not WSL), set `NPB_MPI_ROOT`, build, and run the demo; verify `reason_code=mpi_segfault` and stderr contains the marker after CG has iterated past the first steps
