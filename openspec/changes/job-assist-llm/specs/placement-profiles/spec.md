## ADDED Requirements

### Requirement: Job-assist invokes the model once on the submit host
When `--agent-profile=job-assist` is set, the system SHALL start at most one
job-level assist after aggregated `JobTelemetry` exists. That assist MUST run
on the submitting CLI host (login node) or the documented allocation head, not
once per compute node, and MUST issue at most one model call per wrap attempt.

#### Scenario: One model call for a multi-node job
- **WHEN** `--agent-profile=job-assist` wraps a two-node allocation and LLM
  credentials are present
- **THEN** exactly one model request is issued after telemetry is written

#### Scenario: Tools-only still launches no model
- **WHEN** `--agent-profile` is omitted or is `tools-only`
- **THEN** no job-assist model HTTP request is made

### Requirement: Node LLM remains unsupported in this change
`--agent-node-llm` MUST NOT start a per-node model runtime. The flag MAY be
parsed and MUST be recorded as unsupported. Compute-node supervisors MUST
continue to load only deterministic tools.

#### Scenario: Node LLM flag does not start a node model
- **WHEN** the user passes `--agent-node-llm` with any profile
- **THEN** no per-node model process is started and the CLI records that the
  flag is unsupported
