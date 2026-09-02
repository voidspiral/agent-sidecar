## Context

See `proposal.md` for motivation. Phase 1 plus `job-assist-llm` already wrap
`srun`, overlap supervisors, classifiers, wrap-time `JobTelemetry`, and a
stdlib `POST /v1/chat/completions` assist. `ProcMonitor.start` no-ops when
`collect_fn` is None, so live jobs produce empty `series/`. `--agent-node-llm`
stays unsupported. OpenCode is available on the login host (`mn`) with
Anthropic-compat env (`ANTHROPIC_*`); DeepSeek chat models used there are
text-only.

Constraints: Python 3.10+; stdlib first; TDD with `unittest` (failing tests
first, then implementation); no network and no real `opencode` binary in unit
tests; no hardcoded user homes; sidecars follow the job; LLM must not scrape
`/proc`; provider keys stay on the submit host; no HTTP fallback from wrap.

## Goals / Non-Goals

**Goals:**

- Run mpi-monitor `collect_loop` in the overlap supervisor until SIGTERM/stop.
- Plot local PNG from series after wrap when a plotter exists.
- Replace wrap-time HTTP job-assist with one injectable OpenCode spawn.
- Ship rewritten OpenCode standing docs/skills for this sidecar.
- Provide a launch-failure fixture whose OpenCode note proposes a corrected
  command in text.

**Non-Goals:**

- Per-node OpenCode, SPANK, automatic `scancel`/`scontrol`, ClusterHelm
  adapters, Cursor CLI/SDK as assist runtime, sending images to DeepSeek.

## Decisions

### 1. Implementation method: TDD

Write failing `unittest` cases first: fake `collect_loop` (no `/proc`), fake
plotter, fake OpenCode runner that writes `assist/job.json`, argv `--match` /
`--agent-match`, fail-soft missing/timeout/failed, no HTTP transport on wrap.
Then implement until tests pass. Live NFS/OpenCode checks are operational,
not unit tests.

**Alternatives:** calling real `opencode` or live `/proc` from unittest
(rejected: flaky, needs keys, violates isolation).

### 2. Collect loop in a supervisor thread, stop file on SIGTERM

```
overlap supervisor
  ProcMonitor.start → thread(collect_loop(match, output_dir, stop_file, …))
  sleep until SIGTERM
  ProcMonitor.stop → write stop_file, join thread
  series/{host}_pid{pid}.jsonl
```

Keep the existing one-shot `collect_fn(ctx) -> samples` path for current
schema tests. Default production path: import `mpi_monitor.collect.collect_loop`
when `collect_fn` is None. Import error → `collect_errors`, empty series.

`--match` is `Path(user argv0).name` unless `--agent-match` is set.
`--interval` defaults to `1.0` (flag `--agent-interval` optional; not required
if supervisor always gets a numeric default).

Supervisor argv MUST include `--match` and `--interval`. `JobContext.match`
and `interval` already exist on the SPI.

**Alternatives:** one-shot collect at start (rejected: ranks are not running
yet); `mpi-monitor wrap` instead of overlap (rejected: this product wraps
`srun`, not mpi-monitor wrap).

### 3. PYTHONPATH = sidecar src + mpi-monitor src

Sidecar `PYTHONPATH` is `agent-sidecar/src` plus
`AGENT_MPI_MONITOR_SRC` or `/shared/mpi-monitor/src`. Strip `AGENT_LLM_*` and
`ANTHROPIC_*` from sidecar env/argv. Do not bake `/root` or `/home/<user>`.

**Alternatives:** vendor mpi-monitor into this repo (rejected: neighbor
package already deployed on NFS).

### 4. Wrap-time plot, then OpenCode

After stop + `summarize_series` / anomalies / `reason_code`:

1. If `series/*.jsonl` exist, call `plot_run` with an injectable plotter.
   Missing matplotlib → skip PNG, keep JSONL.
2. List chart paths on `evidence_paths`.
3. If profile is `job-assist`, spawn OpenCode. Never call `chat_complete`.

```
opencode run --dir <repo_root> "<prompt>"
```

`repo_root` is this package root (where `AGENTS.md` and `.opencode/` live).
Timeout default 120s (`AGENT_OPENCODE_TIMEOUT`). Injectable
`opencode_runner(argv, cwd, timeout, env) -> (rc, stdout, stderr)`.

Prompt JSON is `{summary, anomalies, reason_code, evidence_paths}` plus
instructions: read only those fields; write `assist/job.json`; copy
`suspected_reason`; `actions: []`; on `execution_error` with `pid_count=0`
propose a corrected `agent srun` line; do not invent `reason_code`; do not
send images to the model.

If OpenCode exits 0 but does not write the note, persist stdout as `summary`
when non-empty; otherwise `opencode_failed`. Force `actions: []` on any note
we rewrite.

**Alternatives:** HTTP fallback when OpenCode missing (rejected by operator);
keep both clients (rejected: two prompt contracts).

### 5. Fail-soft codes

| Condition | collect_errors key |
|-----------|--------------------|
| `opencode` not on PATH | `opencode_missing` |
| timeout | `opencode_timeout` |
| non-zero / no note | `opencode_failed` |
| mpi-monitor import fail | `mpi_monitor_import` |

User exit and `reason_code` unchanged. No `scancel`/`scontrol`.

### 6. OpenCode docs and skills

Same standing text in `agent.md` and `AGENTS.md` (OpenCode reads `AGENTS.md`).
`skills.md` is an index. `.opencode/skills/mpi-monitor/SKILL.md` plus
`reference.md` adapted from ClusterHelm slave mpi-monitor skill: JSONL/PNG
contract kept; Master/Slave, `workflow_runner`, `partition_report`,
`deploy-slave.sh` stripped. Collect = overlap supervisor + `collect_loop`.
Charts = interpret `charts/*.png`; do not generate images via the model.
Small launch-failure section: ENOENT / `execution_error` / `pid_count=0` →
did not start; suggest compile to NFS and the exact `agent srun` line.
`.opencode/opencode.json` names a default agent; do not copy `slave-agent`.

### 7. Launch-failure fixture

`examples/launch_fail.sh` documents a missing path. Demo script runs
`agent srun --agent-profile=job-assist … -- /shared/agent-sidecar/examples/no-such-mpi`.
Expect non-zero user exit, `reason_code=execution_error`, OpenCode note with
corrected NFS path / compile step. Happy path remains `examples/mpi_io_load.c`.

## Risks / Trade-offs

- [Empty series if match wrong] → basename of user binary; `--agent-match` override.
- [mpi-monitor missing on node PYTHONPATH] → `AGENT_MPI_MONITOR_SRC` / `/shared/...`; collect error, not crash.
- [OpenCode missing on mn] → `opencode_missing`, stop and report; no HTTP.
- [Keys on compute] → unset `ANTHROPIC_*` and `AGENT_LLM_*` in sidecar env.
- [Model invents reason] → copy tool `reason_code`; never overwrite.
- [OpenCode ignores write-note] → fallback to stdout summary or `opencode_failed`.
- [PNG sent to DeepSeek] → skills forbid it; prompt names paths only.

## Migration Plan

- `tools-only` gains live series/charts with no OpenCode.
- `job-assist` requires `opencode` on the submit host. Unset/missing → collect
  error, same user exit. Rollback: omit the profile flag.
- `AGENT_LLM_*` wrap HTTP is unused; keep `llm.py` only if tests for the
  leftover client still exist, but wrap must not call it. Prefer updating
  job-assist tests to the OpenCode runner so HTTP is not required on the wrap
  path.
- Do not ship node-LLM or `scancel` stubs.

## Open Questions

- Default OpenCode timeout (120s) can be tuned via env without a spec change.
- Whether `agent report` pretty-prints charts can wait; JSON dump plus PNG
  files on disk is enough.
