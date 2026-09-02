## Why

Phase 1 ships node tools and a `JobTelemetry` skeleton, but `--agent-profile=job-assist`
does not call a model, and wrap-time telemetry does not yet carry series summaries or
classified anomalies. Operators on the login host (`mn`) already have a DeepSeek API;
they need the submit-side assist loop that consumes the telemetry contract and writes
an interpretation without scraping `/proc` or replacing tool `reason_code`.

## What Changes

- After sidecars stop, the launch host aggregates series and tool events into a
  complete `JobTelemetry` (`summary`, `anomalies`, authoritative `reason_code`)
  before any model call.
- `--agent-profile=job-assist` starts exactly one login-side (or allocation-head)
  assist that calls an OpenAI-compatible chat API using env/flags only.
- The model prompt uses `summary` and `anomalies` as primary input; raw JSONL is
  referenced only via `evidence_paths`.
- The assist writes a `JobAssistNote` under `assist/` and MAY attach it on
  telemetry as `job_assist`. It MUST NOT change `reason_code`, MUST NOT call
  `scancel`/`scontrol`, and MUST NOT replace the user command exit code.
- API/config failures are recorded as collect errors; `tools-only` still launches
  no model.

## Non-goals

- No ClusterHelm control-plane integration: do not reuse, adapt, or consume
  Master/Slave, `workflow_runner`, `partition_report`, `run-slave.sh`,
  submit/wait, or gateway preflight/exclusion policy.
- No per-node LLM runtime (`--agent-node-llm` stays unsupported).
- No SPANK injector, automatic `scontrol`/`scancel` remediation, or retries
  initiated by the model.
- No Cursor CLI / Cursor SDK as the job-assist runtime.
- No node-resident LLM daemon; no hardcoded user home paths; no required
  third-party HTTP SDK (stdlib only).

## Capabilities

### New Capabilities

- `job-assist-llm`: OpenAI-compatible client, env/flag configuration, prompt
  contract, fail-soft errors, and `JobAssistNote` output for a single
  allocation-wide assist after telemetry is written.

### Modified Capabilities

- `placement-profiles`: `job-assist` actually invokes the configured model once
  on the submit host (or allocation head); `tools-only` remains no-LLM;
  node LLM remains out of this change.
- `job-telemetry`: wrap-time document MUST include numeric series summary and
  tool anomalies before assist; optional `job_assist` listing the note path.

## Impact

- **Code:** `src/agent_sidecar` wrap path, new LLM client module, `assist`
  note for job-level output, CLI profile wiring.
- **Operations:** login host (`mn`) supplies `AGENT_LLM_BASE_URL`,
  `AGENT_LLM_API_KEY`, `AGENT_LLM_MODEL` (DeepSeek OpenAI-compatible). Compute
  nodes do not receive the key and do not call the API.
- **Tests:** unittest with a fake client; no network in unit tests. Live
  DeepSeek checks stay optional and gated.
- **Dependencies:** stdlib `urllib`; no `openai` package.
- **Neighbors:** mpi-monitor and ClusterHelm trees are not edited.
