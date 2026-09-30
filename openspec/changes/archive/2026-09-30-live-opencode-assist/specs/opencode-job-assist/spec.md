## MODIFIED Requirements

### Requirement: Job-assist spawns OpenCode once after telemetry
When job-assist is active (the default, or `--agent-profile=job-assist`), the
system SHALL run OpenCode on the submitting CLI host during the user step
(live watcher) and SHALL spawn one final OpenCode invocation after aggregated
`JobTelemetry` exists. The invocation MUST use the repository as its working
project so standing instructions and skills load. Unit tests MUST inject a
runner and MUST NOT execute a real `opencode` binary.

#### Scenario: One OpenCode spawn for a multi-node job
- **WHEN** `--agent-profile=job-assist` wraps a two-node allocation
- **THEN** a live OpenCode watcher is started with the user step and one
  final OpenCode runner call is made after `telemetry.json` is written

#### Scenario: Tools-only does not spawn OpenCode
- **WHEN** `--agent-profile` is `tools-only`
- **THEN** the OpenCode runner is not invoked

## ADDED Requirements

### Requirement: Live OpenCode uses auto only without a TTY
When wrap has no TTY, live and final OpenCode MUST use non-interactive
`--auto` and MUST NOT read operator prompts from stdin. When wrap has a TTY,
live OpenCode SHALL allow interactive questions without taking over the user
`srun` PMI stdin.

#### Scenario: Scripted wrap uses auto
- **WHEN** job-assist wrap runs without a TTY
- **THEN** OpenCode is invoked with `--auto` and wrap does not wait on stdin
  for a chat prompt

#### Scenario: Interactive wrap does not feed OpenCode into user srun
- **WHEN** job-assist wrap runs on a TTY
- **THEN** the user `srun` stdin is not the OpenCode chat and the operator can
  still converse with the live session (including via a printed attach path)
