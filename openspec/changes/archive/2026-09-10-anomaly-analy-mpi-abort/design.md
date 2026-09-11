## Context

See proposal.md (Why). Wrap already classifies MPI abort from
`events/stderr.tail`, writes `telemetry.json`, and may promote
`assist/live.json` or skip post-job OpenCode when
`AGENT_OPENCODE_FINAL_TIMEOUT=0`. Live OpenCode only ticks when tool
anomalies already exist. There is no offline re-analysis CLI.

Constraints: Python 3.10+; stdlib first; TDD with unittest (failing tests
first); inject OpenCode runners; no ClusterHelm; no compute-node LLM; no
hardcoded user homes.

## Goals / Non-Goals

**Goals:**

- Shared `run_analysis(run_dir, ...)` used by wrap and `agent analy`.
- First real pack: `mpi_abort`; optional launch-fail skeleton.
- MPI abort C fixture + demo for cluster validation.
- Incremental stderr flush during user step.

**Non-Goals:**

- SQLite/`--db`, push ingest, chart boxes, OOM/node_fail/io_stall packs
  as acceptance criteria (routing stubs only for deferred codes).

## Decisions

1. **Implementation method: TDD.** Failing unittest first for pack, CLI,
   wrap wiring, stderr flush; then implement. No real `opencode` in unit
   tests. **Alternative:** cluster-only demos — rejected for CI.

2. **Pack always writes `analysis.json`; `job.json` only if missing.**
   Preserves live promote / LLM notes. **Alternative:** always overwrite
   `job.json` — rejected.

3. **`agent analy` defaults to deterministic-only; `--llm` opt-in.** Offline
   reproducibility. **Alternative:** default OpenCode like job-assist —
   rejected for this CLI.

4. **`--code` opt-in read-only scan** with byte/file caps; search
   `MPI_Abort` and binary basename; never compile/write.

5. **Wrap calls pack with `use_llm=False` after telemetry** when non-ok.
   OpenCode path unchanged and fail-soft.

6. **Stderr incremental flush** from the existing ring buffer on a short
   interval (or every N bytes), final write on exit.

7. **Expansion path (later changes):**
   - OOM (`slurm_oom` / `node_local`): later change with mem-limited fixture.
   - `node_fail`: deferred — fixture/`events/slurm.json` only; no real reboot.
   - `io_stall` / shared-storage slowdown: deferred — synthetic later; no
     real Lustre hang injection.

## Risks / Trade-offs

- [False launch-fail if abort too early] → Fixture works several seconds
  first; demo asserts `pid_count > 0`.
- [Flush races with NFS readers] → Accept brief lag; final flush at exit.
- [Pack vs LLM note conflict] → Never overwrite existing `job.json`.
- [Code scan overreach] → Require `--code`; enforce size limits.

## Migration Plan

- Additive CLI + assist files; existing happy-path demos unchanged.
- Rollback: omit `analy` usage; wrap pack can be gated later if needed.
- Rollback of fixture: remove demo script / binary.

## Open Questions

None for this slice; deferred packs are explicitly out of acceptance.
