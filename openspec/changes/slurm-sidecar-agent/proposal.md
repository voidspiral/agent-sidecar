## Why

Plain `srun` plus a user command starts SLURM tasks but does not expose
process-level CPU, IO, RSS, or MPI/SLURM exception evidence while the job
runs. Operators need a job-lifecycle sidecar that starts with the allocation,
collects that evidence on compute nodes (tools and optional assist agents),
and returns a structured telemetry contract the submitter or a job-level
agent can consume.

## What Changes

- Add a user-space `agent` CLI that wraps `srun` / `sbatch` / `salloc`,
  passing through SLURM arguments and consuming only `--agent-*` flags.
- Inject a per-node supervisor sidecar (overlap step by default; exec-wrapper
  fallback) that follows the job: start with the allocation, stop when the
  user step ends.
- Ship deterministic node tools as sidecar plugins: process resource collect
  (via mpi-monitor), SLURM accounting tap, MPI log scan, node-local diagnosis,
  and optional plots.
- Optionally run a per-node assist agent (read-only `NodeAssistNote`) and/or
  a single job-level assist agent. Default profile is tools-only.
- Emit a `JobTelemetry` document (summaries, anomalies, evidence paths) so
  any LLM consumes contracts rather than raw `/proc` or high-frequency JSONL.

## Non-goals

- No ClusterHelm control-plane integration: do not reuse, adapt, or consume
  Master/Slave, `workflow_runner`, `partition_report`, `run-slave.sh`,
  submit/wait, or gateway preflight/exclusion policy.
- No node-resident collector or LLM daemon that outlives the job.
- No SPANK plugin, TaskProlog-as-the-only-injector, or automatic
  `scontrol`/`scancel` remediation in this change (phase 1).
- No PMPI / LD_PRELOAD as the primary collector; no Grafana/Prometheus
  service; no hardcoded user home paths.

## Capabilities

### New Capabilities

- `agent-launch`: CLI wrapping of `srun`/`sbatch`/`salloc` and job-scoped
  sidecar injection (overlap step, exec-wrapper fallback) without breaking PMI.
- `sidecar-spi`: per-node supervisor and deterministic tool plugin contract
  (`start` / `events` / `stop` / `artifacts`).
- `placement-profiles`: `tools-only` (default), optional `node-assist` and
  `job-assist`, resource budgets, and who may retry.
- `job-telemetry`: job-scoped telemetry document, artifact layout, and
  transport when there is no shared filesystem.
- `slurm-mpi-classify`: SLURM/MPI/node anomaly reason codes and evidence
  mapping used by tools and assist layers.

### Modified Capabilities

- (none; this repository has no baseline specs yet)

## Impact

- **New package:** Python 3.10+ library and `agent` CLI in this repo.
- **Neighbors:** mpi-monitor is the process collect/plot library to call;
  memmon and nodestatus probe techniques inform `node-diag` only. Those
  trees are not edited.
- **Operations:** launch host needs the CLI; compute nodes need `python3`
  and `/proc` (inline payload / srun fetch / SSH). Sidecar CPU/mem budget
  is explicit.
- **Outputs:** per-job directory with `JobTelemetry`, series JSONL, optional
  PNG, optional `NodeAssistNote`.
- **Dependencies:** stdlib first; matplotlib optional; mpi-monitor as an
  external package for process sampling.
