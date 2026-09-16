## Context

See proposal.md (Why). Existing fixtures `mpi_io_load` and
`mpi_fault_segfault` are short C programs. P4 replaces those as the ~60s
cluster demo with NAS NPB 3.4-MPI. CG is the selected kernel: two ranks are
valid, the work is compute plus irregular communication, and Class B
(`niter=75`) is the default duration target on this cluster’s two-node
allocation. Compile and run on mn / NFS; do not use WSL as the cluster.

Constraints: Python 3.10+ unittest TDD; no ClusterHelm; no hardcoded user
homes; do not change `reason_code` semantics.

## Goals / Non-Goals

**Goals:**

- Copy NPB 3.4-MPI into a build workdir, apply a unified diff to `CG/cg.f90`,
  `make cg CLASS=B`, install the binary under `examples/`.
- Rank 0 crashes when the CG timed region reaches 30 seconds (half of the
  ~60s target) after printing the same stderr line as `mpi_fault_segfault`.
  Other ranks `sleep(3)` then `exit(0)` so SLURM does not hang.
- Demo script + `--agent-match` for proc-monitor / eth-monitor.

**Non-Goals:**

- Shipping NAS sources in git.
- Tuning class if wall time is not exactly 60s on a given day.
- New classify/pack codes.

## Decisions

1. **Implementation method: TDD.** Failing unittest first: apply the patch to
   a copy of `CG/cg.f90` (or a checked-in snippet of the iteration loop if
   NPB is absent in CI) and assert the midpoint guard and stderr string.
   Then add build/demo scripts. Live ~60s run is a cluster demo, not CI.

2. **Kernel = CG Class B, 2 ranks.** Table P4 lists CG as the communication
   case with a wide rank constraint. Class A (`niter=15`) is often too short
   on this hardware; Class B (`niter=75`, `na=75000`) is the ~60s target.
   Operators may override `NPB_CG_CLASS`.

3. **Do not vendor NPB.** Require `NPB_MPI_ROOT` (directory containing
   `CG/cg.f90` and `Makefile`). Build copies into
   `$AGENT_SHARED/npb-build/cg-mid-segfault` (default `/shared/npb-build/...`)
   so the original tree stays clean. Alternative considered: git submodule —
   rejected (large, license/copy noise).

4. **Patch the main inverse-power loop**, not a wrapper around the binary.
   Inject after `conj_grad` when `mpi_wtime() - crash_t0 >= 30` seconds
   (`crash_t0` sampled right after `timer_start(1)`). NPB 3.4 `timer_read(n)`
   returns `elapsed(n)` only, which stays 0 until `timer_stop`, so a
   `timer_read(1) >= 30` guard never fires during the timed loop. Class B
   on this two-rank VM is far longer than 60s if run to `niter/2`; wall-clock
   30s matches the P4 ~60s case with a mid-run fault. Survivors must `_exit`
   like `mpi_fault_segfault`. Launch with `srun --mpi=pmi2` (or pmix) so the
   two tasks share `MPI_COMM_WORLD`; bare `srun -n2` on this MPICH/SLURM
   cluster yields two 1-rank worlds.

5. **Null dereference via `iso_c_binding` `c_null_ptr`**, not `MPI_Abort` or
   `raise(SIGSEGV)`, matching the C fixture. Print to unit 0 (stderr) the
   line `rank 0 segfault (null deref)` so existing classify/pack keep working.

6. **`--agent-match` uses the installed basename** (for example `cg.B.x`)
   because Linux `comm` is 15 bytes; argv0 matching covers longer names if
   the install name grows.

## Risks / Trade-offs

- [Class B wall time ≠ 60s on this cluster] → Document `NPB_CG_CLASS=A|B`
  override; keep default B.
- [Fortran unit 0 is not stderr on some compilers] → Prefer `write(0,...)`;
  demo checks `events/stderr.tail` for the marker line.
- [Patch fails on a different NPB version] → Pin comments to NPB 3.4.3;
  test apply against a stored loop snippet in tests.
- [mpif90 missing on WSL CI] → Tests do not require compiling CG.

## Migration Plan

Deploy sidecar to `/shared/agent-sidecar`. On mn set `NPB_MPI_ROOT` to the
NPB 3.4-MPI tree, run `scripts/demo_npb_cg_segfault.sh`. Rollback: delete
the example dir and demo script; unmodified NPB tree is untouched.

## Open Questions

None.
