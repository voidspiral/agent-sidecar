## Context

See proposal.md (Why). Wrap today (`run.py`) starts overlap supervisors, blocks
on the user `srun`, then writes `telemetry.json` and, if `profile == "job-assist"`,
calls `run_opencode_assist` once with `opencode run --auto` and stdin `DEVNULL`.
`AgentOptions.profile` defaults to `tools-only`. Node tools already sample for
the job lifetime. OpenCode must stay on the submit host; tests inject runners
and never exec a real `opencode` binary.

Implementation method: TDD (failing unittest first, then code).

## Goals / Non-Goals

**Goals:**

- Default `agent srun` enables job-assist (tools + submit-host OpenCode).
- A live watcher runs on the submit host for the user-step lifetime, ticking
  on artifact snapshots; a final note still runs after wrap-time telemetry.
- Non-TTY wrap never blocks on a chat prompt; TTY conversation does not steal
  the user PMI `srun` stdin.
- Missing OpenCode stays fail-soft.

**Non-Goals:**

- Design-level: no new OpenCode-on-compute protocol; no required tmux; no
  HTTP fallback; no change to overlap injection or mpi-monitor collect.

## Decisions

1. **Default profile is `job-assist`.** Operators who wrap with `agent` want
   assist on. `tools-only` is the explicit opt-out. Alternative: keep
   tools-only default and add a config file — rejected for this change because
   the request is “default start OpenCode”; a later config file can still
   override.

2. **Live path is a submit-host watcher owned by wrap, not a second `srun`.**
   Start it after the run directory exists and overlap (or fallback) has been
   launched, immediately before `run_user`. Stop it in the same bounded join
   as node sidecars. Alternative: `srun --overlap` OpenCode on a compute node
   — rejected (no egress, keys, `/proc` temptation).

3. **Always tick with `--auto`; interactive is attach + stderr, not PMI stdin.**
   A background ticker periodically builds a snapshot (`summarize_series` on
   current `series/` plus `events/`) and invokes the injected OpenCode runner
   with `--auto`. Default interval `15s` via `AGENT_OPENCODE_LIVE_INTERVAL`
   (flags later). When wrap stdin/stdout are TTYs, wrap prints a one-line
   attach hint to stderr and MAY echo tick summaries there; it does not put
   OpenCode on the user `srun` stdin. Non-TTY: ticks only, no hint, no stdin.
   Alternative: foreground OpenCode and background the user step — rejected
   (breaks PMI and batch scripts). Alternative: tmux split — rejected
   (non-goal).

4. **Final note unchanged in contract.** After sidecars stop, write telemetry
   and charts, then one `run_opencode_assist` as today. Live files under
   `assist/` must not overwrite `reason_code`.

5. **Injected `LiveWatcher` protocol for tests:** `start(run_dir)`, `tick()`,
   `stop()`. Default impl shells `opencode`; unit tests never call PATH.

6. **Demos stay non-TTY `--auto`.** `demo_job_assist_mpi.sh` can drop
   `--agent-profile=job-assist` once default flips; they must not require a
   TTY. README shortest command is `agent srun -N3 -n3 -p test -- ./app`.

## Risks / Trade-offs

- [OpenCode cost / rate limits from 15s ticks] → Mitigation: interval env;
  skip a tick when snapshot hash unchanged; fail-soft on timeout.
- [NFS lag: empty series on first ticks] → Mitigation: empty snapshot is
  valid; do not invent `reason_code`.
- [Users expect chat in the same terminal as `srun`] → Mitigation: stderr
  hints + attach command; document second terminal; do not steal PMI stdin.
- [Default job-assist breaks hosts without `opencode`] → Mitigation: already
  specified `opencode_missing`; tools and user exit unchanged.
- [Tests that assume omitted profile is tools-only] → Mitigation: update
  those tests first (TDD).

## Migration Plan

- Flip default in `argv.py`; update unittest profile tests; then watcher;
  then wrap wiring; then README/`AGENTS.md`/`openspec/config.yaml` context
  line about default placement.
- Rollback: `--agent-profile=tools-only` or revert the default.

## Open Questions

- Exact OpenCode attach CLI (`opencode attach` vs printed session id) can be
  chosen at apply time without changing the “second terminal / no PMI steal”
  rule.
