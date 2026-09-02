# job-assist-llm Specification

## Purpose

Defines the submit-side job-assist model loop: how a single allocation-wide
assist is configured, what it may send to an LLM, what it writes back, and how
provider failures stay fail-soft.

## Requirements

### Requirement: Wrap must not issue chat HTTP for job-assist
The wrap path MUST NOT call an OpenAI-compatible `chat/completions` endpoint
when `--agent-profile=job-assist`. Assist MUST go through OpenCode (or a test
injected runner). Missing OpenCode MUST fail-soft with `opencode_missing` and
MUST NOT fall back to HTTP.

#### Scenario: Job-assist does not POST chat completions
- **WHEN** `--agent-profile=job-assist` runs with an injected OpenCode runner
- **THEN** no chat HTTP transport is invoked

#### Scenario: Missing OpenCode has no HTTP fallback
- **WHEN** `--agent-profile=job-assist` runs and OpenCode is missing
- **THEN** no `chat/completions` request is made and a collect error
  `opencode_missing` is recorded

### Requirement: Prompt is the telemetry contract
The model prompt MUST include `summary`, `anomalies`, and `reason_code` from
`JobTelemetry`. The prompt MUST NOT embed every JSONL sample line. Raw series
MAY be named only via `evidence_paths`.

#### Scenario: Prompt carries summary not samples
- **WHEN** job-assist runs after a series with many JSONL lines
- **THEN** the request body contains the numeric summary and anomaly list and
  does not contain every series sample

#### Scenario: Tool reason_code is sent unchanged
- **WHEN** tools classified `mpi_abort`
- **THEN** the prompt's `reason_code` is `mpi_abort`

### Requirement: JobAssistNote is written under assist
After a successful model response, the system SHALL write a `JobAssistNote`
under the run `assist/` directory. The note MUST include an interpretation
text and MUST reference the tool `reason_code`. `actions` MUST be empty or
omit SLURM mutation commands.

#### Scenario: Note lands under assist
- **WHEN** the model returns a valid interpretation
- **THEN** `assist/` contains a job-level note file and telemetry lists it
  under `job_assist` and `evidence_paths`

#### Scenario: Note does not mutate SLURM
- **WHEN** the model text mentions cancelling the job
- **THEN** the stored note does not invoke `scancel` or `scontrol`

### Requirement: Model must not replace the primary reason_code
Job-assist MUST NOT overwrite `JobTelemetry.reason_code` with a model-invented
code. The tool (or documented roll-up) code remains authoritative.

#### Scenario: Authoritative code is preserved
- **WHEN** tools set `reason_code` to `slurm_oom` and the model comments
  "maybe timeout"
- **THEN** `telemetry.json` still has `reason_code` `slurm_oom`

### Requirement: Provider failures are fail-soft
Timeouts, non-success HTTP statuses, and unparseable responses MUST be recorded
as collect errors. They MUST NOT hang the CLI indefinitely and MUST NOT replace
the user command exit code.

#### Scenario: HTTP error keeps user exit
- **WHEN** the chat endpoint returns a non-success status
- **THEN** the CLI exit code remains the user command's code and telemetry
  records a collect error for the assist

#### Scenario: Timeout is bounded
- **WHEN** the chat request exceeds the configured timeout
- **THEN** the CLI proceeds without waiting indefinitely and still writes
  `JobTelemetry`
