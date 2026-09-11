## Why

Wrap and `agent analy` already handle `mpi_abort` with a deterministic pack,
but a single-rank segfault produces different stderr (SIGSEGV / signal 11 /
fixture `rank N segfault`) and today falls through to `slurm_failed` or
`execution_error` without a dedicated Chinese analysis note.

## What Changes

- Add an MPI segfault fault fixture (`mpi_fault_segfault`) and demo script.
- Extend MPI classification with `reason_code=mpi_segfault`.
- Add deterministic `mpi_segfault` analysis pack (phase-1 ask-for-source,
  phase-2 `--code`) wired through `select_pack` / `run_analysis`.
- Add OpenCode skill `mpi-segfault` and README demo notes.
- Keep OOM / node_fail / io_stall out of this change.

## Capabilities

### New Capabilities

- (none — reuse `job-analysis`)

### Modified Capabilities

- `slurm-mpi-classify`: Detect segfault / SIGSEGV / signal 11 patterns and
  emit `mpi_segfault`.
- `job-analysis`: Add `mpi_segfault` pack scenarios (phase-1/2 mirror of
  `mpi_abort`).
- `agent-launch`: Wrap / `analy` route `mpi_segfault` to the dedicated pack;
  document segfault demo expectations.

## Impact

- Classify: [`src/agent_sidecar/classify.py`](src/agent_sidecar/classify.py)
- Analysis: `src/agent_sidecar/analysis/mpi_segfault.py`, packs, runner
- Examples / demos: `examples/mpi_fault_segfault.c`, `scripts/demo_mpi_segfault.sh`
- OpenCode: `.opencode/skills/mpi-segfault/`
- Tests under `tests/` (TDD, no real `opencode` exec)

## Non-goals

- Multi-rank simultaneous crash, generic `mpi_signal`, core-dump parsing,
  OOM / node_fail / io_stall packs, LLM inventing `reason_code`, compute-node
  OpenCode, auto `scancel`.
