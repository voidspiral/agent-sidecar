## MODIFIED Requirements

### Requirement: Job-assist spawns OpenCode once after telemetry
When `--agent-profile=job-assist` is set, wrap SHALL write a submit-host
`JobAssistNote` after aggregated `JobTelemetry` exists. Wrap MUST NOT spawn
OpenCode by default. Wrap MAY spawn at most one OpenCode invocation on the
submitting CLI host when `AGENT_OPENCODE_FINAL_TIMEOUT` is a positive number.
The invocation MUST use the repository as its working project. Unit tests
MUST inject a runner and MUST NOT execute a real `opencode` binary.

#### Scenario: Default wrap writes a note without OpenCode
- **WHEN** `--agent-profile=job-assist` wraps a job and
  `AGENT_OPENCODE_FINAL_TIMEOUT` is unset
- **THEN** `assist/job.json` exists after `telemetry.json` and the OpenCode
  runner is not invoked

#### Scenario: Positive FINAL_TIMEOUT restores wrap OpenCode
- **WHEN** `AGENT_OPENCODE_FINAL_TIMEOUT` is `20`
- **THEN** exactly one OpenCode runner call is made after `telemetry.json` is
  written

#### Scenario: Tools-only does not spawn OpenCode
- **WHEN** `--agent-profile` is `tools-only`
- **THEN** the OpenCode runner is not invoked
