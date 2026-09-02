## RENAMED Requirements

- FROM: `### Requirement: Default profile is tools-only`
- TO: `### Requirement: Default profile is job-assist`

## MODIFIED Requirements

### Requirement: Default profile is job-assist
When `--agent-profile` is omitted, the system SHALL run `job-assist`: per-node
supervisors and tools plus submit-host OpenCode. `--agent-profile` MUST accept
`tools-only`, `node-assist`, and `job-assist`. `--agent-profile=tools-only`
SHALL run node tools only and MUST NOT start OpenCode.

#### Scenario: Omitted profile is tools-only
- **WHEN** the user runs `agent srun --agent-skills=proc-monitor -- ./app`
- **THEN** tool sidecars start and submit-host OpenCode (live watcher and/or
  final note) is attempted; no per-node model is launched

#### Scenario: Omitted profile is job-assist
- **WHEN** the user runs `agent srun --agent-skills=proc-monitor -- ./app`
- **THEN** tool sidecars start and submit-host OpenCode (live watcher and/or
  final note) is attempted; no per-node model is launched

#### Scenario: Explicit tools-only skips OpenCode
- **WHEN** the user runs `agent srun --agent-profile=tools-only -- ./app`
- **THEN** only tool sidecars start; the OpenCode runner is not invoked

#### Scenario: Invalid profile fails closed
- **WHEN** `--agent-profile=clusterhelm` or another unknown value is passed
- **THEN** the CLI SHALL exit non-zero before launching SLURM

### Requirement: Job-assist is a single allocation-wide consumer
Profile `job-assist` SHALL start at most one job-level assist agent for the
allocation (submit host, batch script head, or `SLURM_NODEID=0`). That agent
MUST consume tool summaries and events during the job and aggregated
`JobTelemetry` after wrap, not raw per-sample JSONL as the primary input.

#### Scenario: One job-agent for two nodes
- **WHEN** `--agent-profile=job-assist` is used on a two-node allocation
- **THEN** exactly one job-assist process runs and it receives artifact
  snapshots then the aggregated telemetry document

### Requirement: Job-assist invokes the model once on the submit host
When job-assist is active (the default, or `--agent-profile=job-assist`), the
system SHALL start at most one job-level assist on the submitting CLI host
(login node) or the documented allocation head, not once per compute node. It
MUST NOT issue an OpenAI-compatible HTTP chat from wrap. Live ticks plus one
final note count as that single assist agent, not as per-node models.

#### Scenario: One model call for a multi-node job
- **WHEN** `--agent-profile=job-assist` wraps a two-node allocation and LLM
  credentials are present
- **THEN** OpenCode runs only on the submit host (live during the job and one
  final note after telemetry) and no chat HTTP request is made

#### Scenario: Tools-only still launches no model
- **WHEN** `--agent-profile` is `tools-only`
- **THEN** no job-assist model HTTP request is made and OpenCode is not started

### Requirement: Job-assist invokes OpenCode once on the submit host
When job-assist is active (the default, or `--agent-profile=job-assist`), the
system SHALL start at most one job-level OpenCode assist on the submitting CLI
host, not once per compute node. That assist SHALL run live while the user
step is running and SHALL issue one final note after aggregated `JobTelemetry`
exists. It MUST NOT issue an OpenAI-compatible HTTP chat from wrap.

#### Scenario: One OpenCode call for a multi-node job
- **WHEN** `--agent-profile=job-assist` wraps a two-node allocation
- **THEN** a submit-host OpenCode watcher is active during the user step and
  one final OpenCode note runs after `telemetry.json` is written

#### Scenario: Tools-only still launches no model
- **WHEN** `--agent-profile` is `tools-only`
- **THEN** no OpenCode runner and no chat HTTP request is made
