# placement-profiles Specification

## Purpose

Defines which intelligence runs beside a SLURM job: deterministic node tools by default, optional per-node assist, and optional single job-level assist, including resource budgets and retry authority.

## Requirements

### Requirement: Default profile is job-assist
When `--agent-profile` is omitted, the system SHALL run `job-assist`: per-node
supervisors and tools plus submit-host OpenCode. `--agent-profile` MUST accept
`tools-only`, `node-assist`, and `job-assist`. `--agent-profile=tools-only`
SHALL run node tools only and MUST NOT start OpenCode.

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

### Requirement: Node-assist is optional and read-only
Profile `node-assist` SHALL start at most one assist agent per job id and host. That agent MUST read local tool artifacts and events only, MUST write a `NodeAssistNote`, and MUST NOT call `scancel` or `scontrol`. A node LLM MUST start only when `--agent-node-llm` is also set; without that flag, node-assist MAY be a rule/skill diagnoser with no model.

#### Scenario: Node-assist without LLM flag
- **WHEN** `--agent-profile=node-assist` is set and `--agent-node-llm` is absent
- **THEN** a non-model diagnoser writes `NodeAssistNote` from local artifacts and no model runtime is started

#### Scenario: Node-assist cannot remediates SLURM
- **WHEN** a node-assist agent observes `mpi_abort` on its host
- **THEN** it records a note and MUST NOT invoke `scancel` or `scontrol`

#### Scenario: One node-agent per host
- **WHEN** node-assist is enabled on a node that already has a node-agent for that job
- **THEN** a second agent MUST NOT start

### Requirement: Job-assist is a single allocation-wide consumer
Profile `job-assist` SHALL start at most one job-level assist agent for the
allocation (submit host, batch script head, or `SLURM_NODEID=0`). That agent
MUST consume tool summaries and events during the job and aggregated
`JobTelemetry` after wrap, not raw per-sample JSONL as the primary input.
Live OpenCode ticks MUST run only when tool anomalies exist.

#### Scenario: One job-agent for two nodes
- **WHEN** `--agent-profile=job-assist` is used on a two-node allocation
- **THEN** exactly one job-assist process runs and it receives artifact
  snapshots then the aggregated telemetry document

### Requirement: Combined profiles do not double-retry
When node-assist and job-assist both run, only the job-assist agent or the submit-side CLI MAY initiate a retry. Node-assist MUST NOT retry the user command.

#### Scenario: Only job-level retry
- **WHEN** both P2 and P3 are enabled and a classified exception sets `retry_allowed`
- **THEN** at most one retry is attempted, and it is not initiated by a per-node agent

### Requirement: Sidecar resource budgets
Tool supervisors SHALL request a documented small CPU and memory bound (at most one CPU and 256 MiB unless overridden by flags). A node LLM, when enabled, MUST use a separate overlap step or an explicitly larger bound and MUST NOT request GPUs by default. All assist processes MUST be terminated when the job ends.

#### Scenario: Tools stay within default bound
- **WHEN** tools-only overlap injection is used without override flags
- **THEN** the supervisor step is launched with `--ntasks-per-node=1` and a memory request no greater than 256 MiB

#### Scenario: Node LLM is killed at job end
- **WHEN** `--agent-node-llm` was set and the user step returns
- **THEN** the node-agent process is signaled and does not remain after the bounded join

### Requirement: Job-assist invokes the model once on the submit host
When job-assist is active (the default, or `--agent-profile=job-assist`), the
system SHALL start at most one job-level assist on the submitting CLI host
(login node) or the documented allocation head, not once per compute node. It
MUST NOT issue an OpenAI-compatible HTTP chat from wrap. Live ticks run only
when tool anomalies exist. A final note still follows the OpenCode timeout
rules below. Live ticks plus one final note count as that single assist
agent, not as per-node models.

#### Scenario: One model call for a multi-node job
- **WHEN** `--agent-profile=job-assist` wraps a two-node allocation and LLM
  credentials are present
- **THEN** OpenCode runs only on the submit host (live during the job only
  when tool anomalies exist, and one final note after telemetry when the
  final-timeout rules allow it) and no chat HTTP request is made

#### Scenario: Tools-only still launches no model
- **WHEN** `--agent-profile` is `tools-only`
- **THEN** no job-assist model HTTP request is made and OpenCode is not started

### Requirement: Job-assist invokes OpenCode once on the submit host
When job-assist is active (the default, or `--agent-profile=job-assist`), the
system SHALL start at most one job-level OpenCode assist on the submitting CLI
host, not once per compute node. That assist SHALL run a live watcher while
the user step is running and SHALL issue one final note after aggregated
`JobTelemetry` exists when final-timeout rules allow it. The live watcher
MUST invoke OpenCode only when tool anomalies exist. A normal completion
(`reason_code=ok` and no tool anomalies) SHALL spawn one final OpenCode
invocation when `AGENT_OPENCODE_FINAL_TIMEOUT` is unset.
`AGENT_OPENCODE_FINAL_TIMEOUT=0` MUST skip that final call. A positive
timeout SHALL also run OpenCode after fault jobs. It MUST NOT issue an
OpenAI-compatible HTTP chat from wrap.

#### Scenario: One OpenCode call for a multi-node job
- **WHEN** `--agent-profile=job-assist` wraps a two-node allocation
- **THEN** a submit-host OpenCode watcher is active during the user step and
  one final OpenCode note runs after `telemetry.json` is written when the
  final-timeout rules allow it

#### Scenario: Tools-only still launches no model
- **WHEN** `--agent-profile` is `tools-only`
- **THEN** no OpenCode runner and no chat HTTP request is made

### Requirement: Node LLM remains unsupported in this change
`--agent-node-llm` MUST NOT start a per-node model runtime or OpenCode. The
flag MAY be parsed and MUST be recorded as unsupported. Compute-node
supervisors MUST continue to load only deterministic tools.

#### Scenario: Node LLM flag does not start a node model
- **WHEN** the user passes `--agent-node-llm` with any profile
- **THEN** no per-node model or OpenCode process is started and the CLI
  records that the flag is unsupported
