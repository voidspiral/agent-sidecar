## Purpose

Defines stable SLURM, MPI, and node anomaly reason codes plus the evidence mapping tools and assist agents use so classification stays deterministic and ahead of any LLM.

## ADDED Requirements

### Requirement: Deterministic classification precedes assist
Tool plugins SHALL classify anomalies into a documented reason-code set before any assist agent runs. An LLM MUST NOT invent a replacement primary `reason_code` for the job; it MAY add interpretation in `NodeAssistNote` or a job-assist comment that references the tool code.

#### Scenario: Tool code is authoritative
- **WHEN** mpi-scan emits `mpi_abort` and job-assist also comments
- **THEN** `JobTelemetry.reason_code` remains `mpi_abort` (or a documented roll-up that still lists `mpi_abort` in `anomalies`)

#### Scenario: No samples is not a hang
- **WHEN** no matching PIDs appear before ready timeout and the user command succeeded
- **THEN** telemetry records a collection-incomplete style code or empty series without blocking the CLI on a collector loop

### Requirement: SLURM state codes
`slurm-tap` SHALL map observable SLURM job or step states to at least: `slurm_oom` (OUT_OF_MEMORY), `node_fail` (NODE_FAIL), `timeout` (TIMEOUT), `cancelled` (CANCELLED), and a generic `slurm_failed` for other unsuccessful terminal states when no more specific code applies.

#### Scenario: OOM from accounting
- **WHEN** `sacct` or `scontrol` reports OUT_OF_MEMORY for the job
- **THEN** anomalies include `slurm_oom` with an evidence path to the captured accounting snippet

#### Scenario: Node fail
- **WHEN** the job state is NODE_FAIL
- **THEN** anomalies include `node_fail`

### Requirement: MPI runtime codes
`mpi-scan` SHALL detect documented patterns in captured stdout/stderr including `MPI_Abort`, PMIx abort, disconnected rank, and Hydra `assert (!closed)`, and MUST emit `mpi_abort` or a more specific documented code with a stderr tail path.

#### Scenario: MPI_Abort in stderr
- **WHEN** tee'd output contains `MPI_Abort`
- **THEN** an event with reason code `mpi_abort` is present and `evidence_paths` includes the stderr capture

#### Scenario: No match yields no mpi event
- **WHEN** stderr has no documented MPI fault pattern
- **THEN** mpi-scan MUST NOT emit `mpi_abort`

### Requirement: Resource-efficiency and node-local codes
From process series and node-diag, the system SHALL be able to emit `cpu_idle`, `mem_overalloc`, `rank_imbalance`, `io_stall`, and `node_local` when documented thresholds are met. Thresholds MUST come from flags or config, not hardcoded cluster names.

#### Scenario: CPU idle on allocated cores
- **WHEN** sampled CPU stays below the configured idle threshold for the configured duration while the job is running
- **THEN** anomalies include `cpu_idle`

#### Scenario: Node-local OOM killer
- **WHEN** node-diag observes an OOM killer trace for a sampled pid
- **THEN** anomalies include `node_local` or `slurm_oom` with evidence from the node-diag artifact

### Requirement: Retry metadata is explicit and bounded
Telemetry SHALL set `retry_allowed` true only for documented transient launcher or injection failures (for example overlap rejected before the user command started). Application non-zero exits MUST set `retry_allowed` false. At most one retry is permitted for a given job attempt chain.

#### Scenario: Application failure is not retried
- **WHEN** the user binary exits non-zero after starting
- **THEN** `retry_allowed` is false

#### Scenario: Injection fallback is a classified retry
- **WHEN** overlap injection fails before the user command starts and exec-wrapper has not yet been tried
- **THEN** `retry_allowed` is true and `attempt` is 1
