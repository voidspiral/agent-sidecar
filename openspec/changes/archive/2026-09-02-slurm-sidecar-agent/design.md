## Context

See `proposal.md` for motivation. This repository is empty aside from OpenSpec
scaffolding. Neighbor tree `mpi-monitor` is the process collect/plot library to
call. ClusterHelm tool implementations (`memmon.py`, nodestatus probe style)
inform `node-diag` only. ClusterHelm's control plane is not a design input.

Constraints: Python 3.10+; stdlib first; matplotlib optional; compute nodes may
have no package install; no hardcoded home paths; TDD with `unittest` (failing
tests first, then implementation). Sidecars follow the SLURM job. LLM must not
scrape `/proc` as the primary collector.

## Goals / Non-Goals

**Goals:**

- Package a job-scoped `agent` CLI whose happy path is `agent srun`.
- Inject one per-node supervisor (overlap step, exec-wrapper fallback) that
  loads deterministic tool plugins.
- Emit `JobTelemetry` plus series/charts; optional `NodeAssistNote`.
- Keep remote collection deploy-free (inline payload, `srun` fetch, or SSH).

**Non-Goals:**

- SPANK, TaskProlog-only injection, automatic `scontrol`/`scancel` remediate.
- ClusterHelm adapter (`partition_report`, `workflow_runner`, Master/Slave).
- Node-resident daemons, PMPI as the primary sampler, Grafana.

## Decisions

### 1. Two orthogonal axes: launch vs placement

Launch answers how the sidecar starts with SLURM. Placement answers what runs
on the node after start. Phase 1 implements launch A+C with B fallback, and
placement P1 (`tools-only`) plus a non-model P2 `NodeAssistNote`. P3 job-assist
LLM is specified but deferred from the first implementation slice.

**Alternatives:** folding placement into the launcher (rejected: overlap vs
exec-wrapper must not fork a node LLM per rank).

### 2. Implementation method: TDD

Write failing `unittest` cases first: argv split (`--agent-*` vs SLURM),
supervisor uniqueness, plugin SPI fakes, telemetry schema, reason-code maps,
overlap-vs-fallback with a stub launcher. Then implement until tests pass.
Live SLURM tests are optional and gated. No network in unit tests.

### 3. Package layout and CLI surface

```
src/agent_sidecar/     # library: argv, launch, supervisor, plugins, telemetry
tests/                 # unittest
pyproject.toml         # console script `agent`
```

CLI:

- `agent srun [--agent-profile=...] [--agent-skills=...] [--agent-output-dir DIR] [srun-args] -- CMD...`
- `agent sbatch` / `agent salloc` (env export + passthrough)
- `agent supervisor --job-id ID --host HOST --output-dir DIR --skills LIST`
- `agent report --run-dir DIR` (build/print telemetry from artifacts)

Flags and config files only. Never `/home/<user>/...` literals.

**Alternatives:** wrapping as a Python `-m` only (worse UX than `agent srun`);
one subprocess per skill (rejected by sidecar-spi).

### 4. Default injector: overlap step, then exec-wrapper

Default:

```
srun --overlap --ntasks-per-node=1 --exact --mem=256M agent supervisor ...
srun <user args>   # PMI lives here
```

If overlap fails before the user command starts, retry once with exec-wrapper:
fork collector, parent `execve` user binary so PMI pid is the app. Node-assist
MUST remain one process per node, not one per rank.

**Alternatives:** SPANK (phase 2); TaskProlog (admin, per-rank, drain risk);
`srun bash -c 'mon & exec app'` (forbidden; breaks PMI and over-spawns).

### 5. Supervisor SPI and phase-1 tools

One supervisor per (`SLURM_JOB_ID`, host). Plugins implement `start`, `events`,
`stop`, `artifacts`.

| Tool | Role | Source |
|------|------|--------|
| `proc-monitor` | PID CPU/RSS/IO JSONL | call `mpi-monitor` collect |
| `slurm-tap` | `scontrol`/`sstat`/`sacct` | this repo |
| `mpi-scan` | stderr pattern library | this repo |
| `node-diag` | local OOM/cgroup/fs signals | rewrite using memmon/nodestatus techniques |
| `plot` | optional PNG | `mpi-monitor` plot |

Events are anomalies only. User step exit code is never replaced by collect
errors.

### 6. Placement profiles

- `tools-only` (default): supervisors + tools, no LLM.
- `node-assist`: one read-only diagnoser per host; `--agent-node-llm` required
  to start a model. Writes `NodeAssistNote`. No `scancel`/`scontrol`.
- `job-assist`: one allocation-wide consumer of `JobTelemetry`. If both
  node-assist and job-assist run, only job-assist or the submit CLI may retry.

Phase 1 implements tools-only and non-model node-assist. Job-assist process
may write a stub that formats telemetry without calling a model.

### 7. JobTelemetry and transport

Run directory:

```
{output_dir}/{run_id}/
  telemetry.json
  meta.json
  series/{host}_pid{pid}.jsonl
  charts/                  # optional
  events/
  assist/                  # NodeAssistNote
```

`telemetry.json` holds `summary`, `anomalies`, `evidence_paths`, `reason_code`,
optional `node_assist`, `retry_allowed`, `attempt`. Assist layers read this
document, not raw JSONL.

No shared FS: write `$TMP/agent-sidecar/{job_id}/{host}/`, fetch after stop
via `srun`, SSH, or the mpi-monitor-style inline payload. Fetch is timeout
bounded; failures land in collect errors.

### 8. Classification before any LLM

`slurm-mpi-classify` maps SLURM states (`slurm_oom`, `node_fail`, `timeout`,
`cancelled`, `slurm_failed`), MPI patterns (`mpi_abort`), and series/node
thresholds (`cpu_idle`, `mem_overalloc`, `rank_imbalance`, `io_stall`,
`node_local`). Thresholds come from flags/config. `retry_allowed` is true only
for documented transient injection/launcher failures before the app starts.

### 9. Non-SLURM fallback

When `srun` is not available, `agent srun` SHALL fail closed unless the user
passes an explicit `--agent-launcher=` (e.g. `mpirun`) together with `--hosts`.
That path delegates process wrap to `mpi-monitor wrap` and still writes
`JobTelemetry`. It is a compatibility hatch, not the SLURM happy path.

## Risks / Trade-offs

- [Site disables overlap] → one documented fallback to exec-wrapper; record
  in telemetry; never per-rank bash.
- [PMIx assumes task pid] → prefer overlap so user `srun` is unmodified; test
  exec-wrapper only as fallback.
- [Sidecar steals cores] → `--exact --mem=256M --ntasks-per-node=1`; node LLM
  is a separate opt-in step.
- [No shared FS / missing python3] → inline payload + bounded fetch; per-host
  errors; CLI exit stays the user command.
- [Short jobs, 1s interval] → inherit mpi-monitor `--interval`; empty series
  is allowed.
- [LLM on compute node] → default off; SIGTERM at job end; no GPU by default.

## Migration Plan

- New repo: no production migration. Tag after unittest pass.
- Install the CLI on the launch host; compute nodes need `python3` + `/proc`.
- Rollback: stop wrapping with `agent`; leftover supervisors die with the job.
- SPANK and automatic remediate stay future changes; do not ship stubs that
  call `scancel`.

## Open Questions

- Config file format (`toml` vs flags-only) can wait; flags are enough for v1.
- Exact idle/imbalance numeric defaults can be set in implementation tests
  without changing specs.
- Whether `agent` the console script name collides with other packages on a
  given site is an install-time choice (`agent-sidecar` extra script if needed).
