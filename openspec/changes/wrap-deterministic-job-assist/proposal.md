## Why

Wrap-end `opencode run` takes 60–70s on every MPI job, including healthy
`reason_code=ok` runs that never triggered live OpenCode. Operators still need
a numbered Simplified Chinese note with **resource-based suggestions**
(CPU/RSS/IO/ethernet peaks, host/pid counts). A cold OpenCode agent loop is
the wrong default for that.

## What Changes

- **BREAKING** (job-assist wrap default): wrap does **not** spawn post-job
  OpenCode unless `AGENT_OPENCODE_FINAL_TIMEOUT` is a positive number.
- Wrap still writes `assist/job.json` for healthy jobs via deterministic
  **resource hints** from `telemetry.json` `summary` (never omit the 建议 item).
- When a deterministic pack already wrote `assist/job.json`, wrap **keeps** it
  and does not unlink it to re-run OpenCode.
- Live promote of `assist/live.json` is unchanged.
- `agent analy --llm` still may spawn OpenCode (manual review).
- Standing job-assist docs and README describe wrap-default hints vs optional
  wrap OpenCode escape hatch.

## Non-goals

- No ClusterHelm control-plane integration: do not reuse, adapt, or consume
  Master/Slave, `workflow_runner`, `partition_report`, `run-slave.sh`,
  submit/wait, or gateway preflight/exclusion policy.
- No persistent `opencode serve`, HTTP chat fallback, or compute-node OpenCode.
- No scraping `/proc` or embedding full JSONL bodies in the note.
- No SPANK injector or automatic `scancel`/`scontrol`.
- Does not remove live OpenCode ticks on tool anomalies.

## Capabilities

### New Capabilities

- `resource-hints`: wrap-time numbered Chinese `JobAssistNote` from telemetry
  summary heuristics (including healthy jobs), always with a 建议 item.

### Modified Capabilities

- `opencode-job-assist`: wrap default is zero OpenCode spawns; positive
  `AGENT_OPENCODE_FINAL_TIMEOUT` remains the wrap OpenCode escape hatch.
- `placement-profiles`: job-assist wrap assist is deterministic by default.
- `job-telemetry`: job-assist note may come from resource hints or a pack,
  not only from a model.
- `agent-launch`: wrap still runs packs on non-ok; ok jobs still get
  `assist/job.json` with suggestions.

## Impact

- **Code:** `run_job_assist`, new `analysis/resource_hints.py`, wrap tests.
- **Ops:** healthy MPI wrap returns in milliseconds with Chinese advice; set
  `AGENT_OPENCODE_FINAL_TIMEOUT` to a positive value to restore wrap OpenCode.
- **Tests:** unittest fakes only; no real `opencode` binary.
- **Docs:** AGENTS.md lockstep copies, README EN/ZH.
