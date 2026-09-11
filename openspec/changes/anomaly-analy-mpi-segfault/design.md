## Context

See proposal.md (Why). `mpi_abort` pack, `agent analy`, and wrap wiring
already exist. Classification only matches abort-family stderr; a null-deref
segfault on one rank is unclassified as MPI-specific today.

Constraints: Python 3.10+; stdlib first; TDD with unittest; no ClusterHelm;
no compute-node LLM; no hardcoded user homes; do not overwrite tool
`reason_code`.

## Goals / Non-Goals

**Goals:**

- Fixture `mpi_fault_segfault`: busy then single-rank null deref; prints
  `rank N segfault (null deref)` before crash.
- Classify `mpi_segfault` from fixture line plus common launcher phrases
  (`Segmentation fault`, `SIGSEGV`, `signal 11`).
- Pack `mpi_segfault` with phase-1/2 behavior identical in contract to
  `mpi_abort` (Chinese numbered summary, `needs_source`, `--code`).
- Demo script and OpenCode skill.

**Non-Goals:**

- Multi-rank crash matrices, `mpi_signal` umbrella code, core dumps,
  OOM / node_fail / io_stall acceptance.

## Decisions

1. **Implementation method: TDD.** Failing unittest first for classify and
   pack; then implement. Synthetic `stderr.tail` is enough for CI; cluster
   demo validates live launcher text.

2. **`reason_code` / pack name: `mpi_segfault`.** Orthogonal to `mpi_abort`.
   Segfault patterns MUST NOT match abort-only strings.

3. **Fixture stderr line is authoritative for demos.** Launcher patterns are
   additional classify coverage so OpenMPI/PMIx wording still maps.

4. **Trigger via null write**, not `MPI_Abort` or `raise(SIGSEGV)`, so
   classify stays orthogonal and code_scan can prefer the fixture source.

5. **Reuse `run_analysis` / phase-1/2 rules** from the existing job-analysis
   main spec; only add pack-specific parsing and Chinese templates.

6. **Expansion unchanged:** OOM later; node_fail / io_stall deferred.

## Risks / Trade-offs

- [Launcher wording variance] → Cover several regexes; fixture line guarantees
  demo classification.
- [False positive on unrelated "signal 11" noise] → Prefer lines with rank /
  Segmentation / SIGSEGV context; fixture line is primary for pack parse.
- [Early crash before samples] → Fixture works several seconds first; demo
  asserts `pid_count > 0`.

## Migration Plan

- Additive classify + pack + demo; existing abort demos unchanged.
- Rollback: remove patterns/pack/demo; routing falls back to generic.

## Open Questions

None for this slice.
