# slurm-mpi-classify Specification

## Purpose

Defines stable SLURM, MPI, and node anomaly reason codes plus the evidence mapping tools and assist agents use so classification stays deterministic and ahead of any LLM.

## Requirements

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
`mpi-scan` SHALL detect documented patterns in captured stdout/stderr including `MPI_Abort`, PMIx abort, disconnected rank, Hydra `assert (!closed)`, segmentation faults, floating-point exceptions, and fixture deadlock markers, and MUST emit `mpi_abort`, `mpi_segfault`, `mpi_fpe`, `mpi_deadlock`, or a more specific documented code with a stderr tail path.

#### Scenario: MPI_Abort in stderr
- **WHEN** tee'd output contains `MPI_Abort`
- **THEN** an event with reason code `mpi_abort` is present and `evidence_paths` includes the stderr capture

#### Scenario: SIGFPE in stderr
- **WHEN** tee'd output contains `Floating point exception`, `SIGFPE`, `signal 8`, or `rank N fpe`
- **THEN** an event with reason code `mpi_fpe` is present

#### Scenario: Deadlock fixture marker in stderr
- **WHEN** tee'd output contains `rank N deadlock`
- **THEN** an event with reason code `mpi_deadlock` is present

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

### Requirement: MPI segfault runtime code
`mpi-scan` / wrap stderr classification SHALL detect documented segfault
patterns and emit `mpi_segfault` with a stderr evidence path. Patterns MUST
include at least: a fixture-style `rank <N> segfault` line, `Segmentation
fault`, `SIGSEGV`, and `signal 11` / `exited (on|with) signal 11` style
launcher phrases. Matching MUST remain orthogonal to `mpi_abort` (abort-only
strings MUST NOT produce `mpi_segfault`).

#### Scenario: Fixture segfault line
- **WHEN** tee'd stderr contains `rank 0 segfault (null deref)`
- **THEN** an event with reason code `mpi_segfault` is present

#### Scenario: Launcher SIGSEGV wording
- **WHEN** stderr contains `Segmentation fault` or `Signal 11` / `SIGSEGV`
  without `MPI_Abort`
- **THEN** classification yields `mpi_segfault`

#### Scenario: Abort remains abort
- **WHEN** stderr contains `rank 0 called MPI_Abort` and no segfault pattern
- **THEN** classification yields `mpi_abort`, not `mpi_segfault`
