## Why

Wrap can classify `MPI_Abort` into `reason_code=mpi_abort`, but with
`AGENT_OPENCODE_FINAL_TIMEOUT=0` and live OpenCode stopping at user-step end,
operators often get telemetry without a deterministic analysis note. There is
no offline CLI to re-run the same investigation after the job ends.

## What Changes

- Add an MPI abort fault fixture (`mpi_fault_abort`) and demo script.
- Add deterministic analysis packs that write `assist/analysis.json` and, when
  needed, `assist/job.json` (Simplified Chinese numbered summary).
- Add `agent analy --run-dir` (optional `--code`, `--llm`) as a submit-host
  offline entry point.
- Call the same pack from wrap when the job is non-ok, independent of OpenCode.
- Incrementally flush `events/stderr.tail` during the user step.
- Add OpenCode skill `mpi-abort`.
- Record expansion path for later packs (OOM later; node_fail / io_stall
  deferred).

## Capabilities

### New Capabilities
- `job-analysis`: Deterministic post-job / offline analysis packs and
  `agent analy` CLI contract (safe bounds, no SLURM mutation).

### Modified Capabilities
- `agent-launch`: Add `analy` subcommand; wrap invokes analysis on non-ok.
- `job-telemetry`: Analysis artifacts listed under assist / evidence when
  packs run; stderr tail may grow during the user step.

## Impact

- CLI: [`src/agent_sidecar/cli.py`](src/agent_sidecar/cli.py)
- Wrap / stdio: [`src/agent_sidecar/run.py`](src/agent_sidecar/run.py)
- New package: `src/agent_sidecar/analysis/`
- Examples / demos: `examples/mpi_fault_abort.c`, `scripts/demo_mpi_abort.sh`
- OpenCode: `.opencode/skills/mpi-abort/`
- Tests under `tests/` (TDD, no real `opencode` exec)

## Non-goals

- Central DB / compute push, chart anomaly boxes, real node reboot, real
  Lustre hang injection, OpenCode on compute nodes, auto `scancel`, model-
  chosen shell toolchains, `--db=` ingest.
