## Purpose

Defines which intelligence runs beside a SLURM job: deterministic node tools by default, optional per-node assist, and optional single job-level assist, including resource budgets and retry authority.

## ADDED Requirements

### Requirement: Default profile is tools-only
When `--agent-profile` is omitted, the system SHALL run `tools-only`: per-node supervisors and tools, no LLM, and no node-assist process. `--agent-profile` MUST accept `tools-only`, `node-assist`, and `job-assist`.

#### Scenario: Omitted profile is tools-only
- **WHEN** the user runs `agent srun --agent-skills=proc-monitor -- ./app`
- **THEN** only tool sidecars start; no node-agent and no job-agent LLM is launched

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
Profile `job-assist` SHALL start at most one job-level assist agent for the allocation (submit host, batch script head, or `SLURM_NODEID=0`). That agent MUST consume aggregated `JobTelemetry`, not raw per-sample JSONL as the primary input.

#### Scenario: One job-agent for two nodes
- **WHEN** `--agent-profile=job-assist` is used on a two-node allocation
- **THEN** exactly one job-assist process runs and it receives the aggregated telemetry document

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
