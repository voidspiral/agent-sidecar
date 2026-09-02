## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Assist uses env or flags for the LLM endpoint
**Reason**: Job-assist no longer POSTs OpenAI-compatible chat from wrap;
OpenCode on the login host is the only assist runtime.
**Migration**: Run `opencode` on the submit host with existing Anthropic-compat
provider env; omit `--agent-profile=job-assist` to skip assist.
