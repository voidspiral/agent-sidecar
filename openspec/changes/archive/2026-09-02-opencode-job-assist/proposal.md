## Why

`--agent-profile=job-assist` currently POSTs DeepSeek `/chat/completions` from wrap
and never starts `mpi-monitor.collect.collect_loop`, so `series/` stays empty,
charts are never written, and the model cannot see CPU/RSS/IO. Operators want
OpenCode on the login host (`mn`) as the assist runtime, with repo-local
`agent.md` / skills, local PNG charts, and a launch-failure path that explains
ENOENT and suggests a corrected `agent srun` line.

## What Changes

- Overlap `proc-monitor` runs `collect_loop` in a background thread until stop;
  supervisor argv includes `--match` and `--interval`.
- After wrap, if series exist, the launch host writes optional PNG charts under
  `charts/` (matplotlib optional; JSONL stays).
- **BREAKING** (job-assist runtime): wrap no longer calls
  `POST .../chat/completions`. `--agent-profile=job-assist` spawns OpenCode once
  on the submit host after `telemetry.json` exists. There is no HTTP fallback.
- OpenCode prompt uses `summary` / `anomalies` / `reason_code` / `evidence_paths`
  only. The note still copies tool `reason_code`, forces `actions: []`, and MUST
  NOT change the user exit code.
- Repo ships `agent.md`, `AGENTS.md`, `skills.md`, and
  `.opencode/skills/mpi-monitor` rewritten for this sidecar (not ClusterHelm).
- A documented missing-binary launch fixture lets OpenCode diagnose start
  failure and propose a corrected command in text.

## Non-goals

- No ClusterHelm control-plane integration: do not reuse, adapt, or consume
  Master/Slave, `workflow_runner`, `partition_report`, `run-slave.sh`,
  submit/wait, or gateway preflight/exclusion policy.
- No per-node LLM / OpenCode on compute nodes (`--agent-node-llm` stays
  unsupported).
- No SPANK injector, automatic `scontrol`/`scancel` remediation, or retries
  initiated by the model.
- No silent fallback to the stdlib HTTP chat client from wrap.
- No sending PNGs to DeepSeek (`deepseek-v4-flash` is text-only); charts are
  local matplotlib / mpi-monitor plot only.
- No Cursor CLI / Cursor SDK as the job-assist runtime.

## Capabilities

### New Capabilities

- `opencode-job-assist`: injectable OpenCode runner after telemetry, prompt
  contract, fail-soft `opencode_*` collect errors, `JobAssistNote` with
  corrected-launch text on start failure, and repo OpenCode skills/docs.

### Modified Capabilities

- `placement-profiles`: `job-assist` spawns OpenCode once on the submit host;
  `tools-only` still launches no model; node LLM remains unsupported.
- `job-telemetry`: wrap-time document lists charts when series exist; series
  come from live collect, not a one-shot empty start.
- `job-assist-llm`: wrap MUST NOT issue OpenAI-compatible HTTP from the
  job-assist path; OpenCode replaces that call.
- `sidecar-spi`: `proc-monitor` MUST sample until stop via `collect_loop`;
  wrap-time plot is optional PNG from JSONL.

## Impact

- **Code:** `proc_monitor`, supervisor CLI, wrap PYTHONPATH, plot after wrap,
  `assist` / new `opencode_assist`, argv `--agent-match`.
- **Ops:** login host must have `opencode` on PATH and existing
  Anthropic-compat env for OpenCode (`ANTHROPIC_*` in the operator env file).
  Compute nodes must not receive those keys.
- **Tests:** unittest with fake `collect_loop`, fake plotter, fake OpenCode
  runner; no live `/proc`, no network, no real `opencode` binary.
- **Neighbors:** mpi-monitor is imported at runtime via `PYTHONPATH` /
  `AGENT_MPI_MONITOR_SRC`; ClusterHelm tree is not imported.
