## ADDED Requirements

### Requirement: Job-assist invokes OpenCode once on the submit host
When `--agent-profile=job-assist` is set, the system SHALL start at most one
job-level assist after aggregated `JobTelemetry` exists. That assist MUST run
on the submitting CLI host (login node) or the documented allocation head, not
once per compute node, and MUST issue at most one OpenCode spawn per wrap
attempt. It MUST NOT issue an OpenAI-compatible HTTP chat from wrap.

#### Scenario: One OpenCode call for a multi-node job
- **WHEN** `--agent-profile=job-assist` wraps a two-node allocation
- **THEN** exactly one OpenCode runner invocation is issued after telemetry is
  written

#### Scenario: Tools-only still launches no model
- **WHEN** `--agent-profile` is omitted or is `tools-only`
- **THEN** no OpenCode runner and no chat HTTP request is made

### Requirement: Node LLM remains unsupported in this change
`--agent-node-llm` MUST NOT start a per-node model runtime or OpenCode. The
flag MAY be parsed and MUST be recorded as unsupported. Compute-node
supervisors MUST continue to load only deterministic tools.

#### Scenario: Node LLM flag does not start a node model
- **WHEN** the user passes `--agent-node-llm` with any profile
- **THEN** no per-node model or OpenCode process is started and the CLI
  records that the flag is unsupported
