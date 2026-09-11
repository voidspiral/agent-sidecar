## Context

See proposal.md (Why). Operators wrap with `python3 -m agent_sidecar srun`
and re-analyze with `agent analy --run-dir` where `--llm` is opt-in.
Quiet wrap already prints `run: {run_dir}`. Packs emit `ask_code_cmd`
pointing at `python3 -m agent_sidecar analy --run-dir`. Default
`--agent-profile` for the module CLI is out of scope (live-opencode-assist).

Constraints: Python 3.10+; stdlib first; TDD with unittest (failing tests
first); inject OpenCode runners; no ClusterHelm; no compute-node LLM; no
hardcoded user homes; `--log` is the sidecar run directory, not a raw
SLURM log file.

## Goals / Non-Goals

**Goals:**

- Two login-host scripts: `sidecar.sh` (wrap + job-assist on tool artifacts)
  and `sidecar-analy.sh` (source-authorized `--code` root-cause, LLM default).
- `--log` / `--run-dir` aliases; `--no-llm` for deterministic analy.
- Next-step text uses `sidecar-analy.sh --log`.

**Non-Goals:**

- Changing omitted-profile behavior for `agent srun` (already `job-assist`).
- Raw `.out` ingest, ClusterHelm.

## Decisions

1. **Implementation method: TDD.** Failing unittest first for CLI flags,
   `AGENT_ENTRY`, scripts, and report next-step; then implement. No real
   `opencode` in unit tests. **Alternative:** bash-only injection of
   `--agent-profile=tools-only` — rejected as harder to unit-test.

2. **`sidecar.sh` is a thin PATH wrapper.** Resolve repo root, prepend
   `src/` to `PYTHONPATH`, exec `python3 -m agent_sidecar "$@"`. Profile
   default remains `job-assist` (same as the module CLI). **Alternative:**
   force `tools-only` via `AGENT_ENTRY` — rejected; wrap must interpret
   skill artifacts on every launch.

3. **`tools-only` is opt-out only.** `--agent-profile=tools-only` skips
   wrap-time OpenCode. `sidecar-analy.sh --code` is the authorized-source
   pass and does not replace the wrap note.

4. **`agent analy` defaults to OpenCode.** `--no-llm` is the deterministic
   path; `--llm` stays accepted. Wrap still calls `run_analysis(...,
   use_llm=False)`. Missing OpenCode remains fail-soft. **Alternative:**
   keep `--llm` opt-in — rejected; operators expect analysis to use LLM.

5. **`--log` is an alias for `--run-dir`.** Same Path; both set and
   unequal → exit 2. Public docs and `ask_code_cmd` use `--log`.
   **Alternative:** drop `--run-dir` — rejected for compatibility.

6. **Quiet report next-step** when `reason_code != ok`: one line naming
   `sidecar-analy.sh --log {run_dir} --code /path/to/src`.

7. **Deploy footer** prints
   `/shared/agent-sidecar/scripts/sidecar.sh` and `sidecar-analy.sh`
   after rsync (whole tree already copied).

## Risks / Trade-offs

- [Operators still use `agent srun` and get wrap-time OpenCode] → Document
  `sidecar.sh` as the public entry; leave module path for power users.
- [Default analy OpenCode hangs CI] → Unit tests inject runners; never
  exec a real `opencode` binary; `--no-llm` for deterministic tests.
- [Conflicting `--log` and `--run-dir`] → Fail closed with stderr.
- [Script not executable after rsync] → Ship `+x` in git; tests assert
  executable bit.

## Migration Plan

- Additive scripts; `--run-dir` and `--llm` still work.
- Rollback: ignore the new scripts; pass `--no-llm` if default OpenCode
  is unwanted.
- Demos: prefer `sidecar.sh` / `sidecar-analy.sh`; job-assist live demos
  pass `--agent-profile=job-assist` or keep calling the module.

## Open Questions

None; `--log` meaning and wrap-vs-analy LLM split are locked in the
proposal.
