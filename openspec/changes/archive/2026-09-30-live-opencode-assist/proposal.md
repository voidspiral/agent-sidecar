## Why

Operators expect `agent srun` to start monitoring and OpenCode by default, and
to interpret problems **while** the SLURM job runs—not only after wrap writes
`telemetry.json`. Today the default profile is `tools-only` (no OpenCode), and
`job-assist` is a single non-interactive `--auto` spawn after the user step
ends, so live diagnosis and conversation never happen during execution.

## What Changes

- **BREAKING**: omitted `--agent-profile` SHALL default to `job-assist` (node
  tools plus submit-host OpenCode). `--agent-profile=tools-only` remains the
  off switch for OpenCode.
- When `job-assist` is active, wrap SHALL start a **live** OpenCode session on
  the submitting CLI host **when the user step starts**, consuming growing
  `series/`, `events/`, and partial summaries—not every JSONL line, and not
  `/proc` on compute nodes.
- If stdin/stdout is a TTY, the live session SHALL be interactive (user can
  ask questions). If not a TTY (scripts, demos, CI), the watcher SHALL use
  non-interactive `--auto` snapshots and MUST NOT block on a prompt.
- Interactive OpenCode MUST NOT steal the user `srun` PMI TTY. Conversation
  happens on the wrap process's TTY only when that does not replace the user
  step; otherwise wrap prints how to attach from a second terminal and keeps
  the user step in the foreground.
- After the user step returns, wrap still writes complete `telemetry.json`
  (and optional charts) and SHALL run one final OpenCode note (`assist/job.json`)
  as today.
- Missing `opencode` remains fail-soft (`opencode_missing`): tools and the user
  command still run; the CLI exit code stays the user command's code.
- Node tools (`proc-monitor`, `slurm-tap`, `mpi-scan`, `node-diag`) stay the
  sole `/proc` and SLURM collectors; OpenCode only reads contracts and paths.

## Non-goals

- No ClusterHelm control-plane integration: do not reuse, adapt, or consume
  Master/Slave, `workflow_runner`, `partition_report`, `run-slave.sh`,
  submit/wait, or gateway preflight/exclusion policy.
- No OpenCode (or any model) on compute nodes; `--agent-node-llm` stays
  unsupported.
- No scraping `/proc` from OpenCode as the primary collector.
- No automatic `scancel` / `scontrol` remediation; `actions` stay `[]`.
- No overwriting tool `reason_code`.
- No HTTP `/chat/completions` fallback.
- No tmux/screen orchestration as a required injector.
- No SPANK plugin.

## Capabilities

### New Capabilities

- `live-opencode-assist`: submit-host watcher that starts with the user step,
  reads growing tool artifacts, supports TTY conversation or non-TTY `--auto`
  ticks, fail-soft when OpenCode is missing, and stops when the job ends.

### Modified Capabilities

- `placement-profiles`: default profile is `job-assist`; `tools-only` opts out
  of OpenCode but still runs node tools.
- `opencode-job-assist`: OpenCode is live during the job plus one final note
  after telemetry; wrap `--auto` only when there is no TTY.
- `job-telemetry`: live assist may write incremental notes under `assist/`
  before the final `telemetry.json`; the wrap-time document remains
  authoritative for `reason_code`.
- `agent-launch`: wrap starts the live submit-host watcher without replacing
  the user PMI `srun` step.

## Impact

- **Code:** wrap lifecycle in `run.py` / CLI; new live watcher beside
  `opencode_assist.py`; default profile in `argv.py`; demos/README drop
  required `--agent-profile=job-assist`.
- **Ops:** login host (`mn`) needs `opencode` for assist; without it, monitoring
  still works. Compute nodes unchanged. OpenCode config stays on the login host.
- **Tests:** unittest with fake live runner (start/tick/stop), fake TTY vs
  non-TTY; no real `opencode`, no live `/proc`.
- **Docs:** `AGENTS.md` / `agent.md` allow during-job analysis from artifact
  snapshots, still forbid `/proc` scrape and compute-node OpenCode.
