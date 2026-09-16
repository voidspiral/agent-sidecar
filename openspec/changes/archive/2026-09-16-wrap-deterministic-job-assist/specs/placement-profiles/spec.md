## MODIFIED Requirements

### Requirement: Job-assist invokes OpenCode once on the submit host
When `--agent-profile=job-assist` is set, the system SHALL start at most one
job-level assist after aggregated `JobTelemetry` exists. That assist MUST run
on the submitting CLI host, not once per compute node. By default the assist
MUST be a deterministic `assist/job.json` write (live promote, pack note, or
resource hints) and MUST NOT spawn OpenCode. A positive
`AGENT_OPENCODE_FINAL_TIMEOUT` MAY spawn at most one OpenCode per wrap
attempt. Wrap MUST NOT issue an OpenAI-compatible HTTP chat.

#### Scenario: Default job-assist wrap has no OpenCode
- **WHEN** `--agent-profile=job-assist` wraps a two-node allocation without
  `AGENT_OPENCODE_FINAL_TIMEOUT`
- **THEN** the OpenCode runner is not invoked and `assist/job.json` exists

#### Scenario: Tools-only still launches no model
- **WHEN** `--agent-profile` is `tools-only`
- **THEN** no OpenCode runner and no chat HTTP request is made
