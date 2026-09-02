## Purpose

Defines submit-host OpenCode job-assist: one bounded `opencode run` after
`JobTelemetry` exists, the prompt contract, fail-soft collect errors, and
text-only corrected-launch advice that must not mutate SLURM.

## ADDED Requirements

### Requirement: Job-assist spawns OpenCode once after telemetry
When `--agent-profile=job-assist` is set, the system SHALL spawn at most one
OpenCode invocation on the submitting CLI host after aggregated `JobTelemetry`
exists. The invocation MUST use the repository as its working project so
standing instructions and skills load. Unit tests MUST inject a runner and
MUST NOT execute a real `opencode` binary.

#### Scenario: One OpenCode spawn for a multi-node job
- **WHEN** `--agent-profile=job-assist` wraps a two-node allocation
- **THEN** exactly one OpenCode runner call is made after `telemetry.json` is
  written

#### Scenario: Tools-only does not spawn OpenCode
- **WHEN** `--agent-profile` is omitted or is `tools-only`
- **THEN** the OpenCode runner is not invoked

### Requirement: Prompt is the telemetry contract plus write-note instructions
The OpenCode prompt MUST include `summary`, `anomalies`, `reason_code`, and
`evidence_paths` from `JobTelemetry`. The prompt MUST NOT embed every JSONL
sample line. The prompt MUST instruct OpenCode to write `assist/job.json` with
copied `suspected_reason`, empty `actions`, and (on launch-style failure) a
corrected launch command in the summary text.

#### Scenario: Prompt carries summary not samples
- **WHEN** job-assist runs after a series with many JSONL lines
- **THEN** the OpenCode prompt contains the numeric summary and anomaly list
  and does not contain every series sample

#### Scenario: Launch failure asks for a corrected command
- **WHEN** `reason_code` is `execution_error` and sampled `pid_count` is 0
- **THEN** the prompt asks OpenCode to explain the start failure and propose
  a corrected `agent srun` line in the note summary

### Requirement: Provider and runner failures are fail-soft
Missing `opencode`, non-zero exit, and timeout MUST be recorded as collect
errors (`opencode_missing`, `opencode_failed`, `opencode_timeout`). They MUST
NOT hang the CLI indefinitely and MUST NOT replace the user command exit code
or overwrite `reason_code`.

#### Scenario: Missing OpenCode keeps user exit
- **WHEN** `--agent-profile=job-assist` runs and `opencode` is not on PATH
- **THEN** no model HTTP fallback is attempted, a collect error
  `opencode_missing` is recorded, telemetry is still written, and the CLI
  exit code remains the user command's code

#### Scenario: Timeout is bounded
- **WHEN** OpenCode exceeds the configured timeout
- **THEN** the CLI proceeds without waiting indefinitely, records
  `opencode_timeout`, and still writes `JobTelemetry`

#### Scenario: Non-zero OpenCode keeps user exit
- **WHEN** the OpenCode runner returns a non-zero status
- **THEN** the CLI exit code remains the user command's code and telemetry
  records `opencode_failed`

### Requirement: Note does not mutate SLURM or reason_code
After a successful OpenCode run that writes a note, `actions` MUST be empty.
The system MUST NOT invoke `scancel` or `scontrol`. `JobTelemetry.reason_code`
MUST remain the tool (or documented roll-up) code.

#### Scenario: Note lands under assist
- **WHEN** OpenCode writes a valid interpretation
- **THEN** `assist/job.json` exists, telemetry lists it under `job_assist` and
  `evidence_paths`, and `reason_code` is unchanged

#### Scenario: Note does not mutate SLURM
- **WHEN** the model text mentions cancelling the job
- **THEN** the stored note has empty `actions` and the sidecar does not invoke
  `scancel` or `scontrol`

### Requirement: Keys stay off compute nodes
OpenCode credentials (`ANTHROPIC_*` and leftover `AGENT_LLM_*`) MUST NOT be
exported into sidecar `srun` argv or sidecar environment.

#### Scenario: Sidecar argv has no provider keys
- **WHEN** job-assist wrap starts overlap supervisors
- **THEN** sidecar argv does not contain API keys and those variables are
  unset in the sidecar process environment
