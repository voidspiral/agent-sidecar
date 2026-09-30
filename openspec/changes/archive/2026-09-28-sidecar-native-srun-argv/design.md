## Context

See proposal.md (Why). Today `parse_agent_argv` treats argv[0] as the
launcher and consumes `--agent-*` only immediately after it. Public
examples therefore look like `sidecar.sh srun --agent-match=… -n2 -- bin`.
`sidecar.sh` stays a thin PYTHONPATH + exec wrapper. `sidecar-analy.sh`
already injects `analy` and owns `--log` / `--code` / `--no-llm`.

Constraints: Python 3.10+; stdlib first; TDD with unittest (failing tests
first); no ClusterHelm; no compute-node LLM; no hardcoded user homes;
`测试.md` is the cluster acceptance script for this change.

## Goals / Non-Goals

**Goals:**

- Leading `--agent-*` before `srun`/`sbatch`/`salloc` in the Python
  parser (so `sidecar.sh --agent-verbose srun -n2 /path/app` works).
- Optional `--` when the user command is not option-shaped.
- Rewrite `测试.md` to the new commands; re-run three real cases on mn.

**Non-Goals:**

- Bash getopts in `sidecar.sh`.
- Renaming `--agent-*` flags.
- Rewriting every existing unittest that still uses `srun --agent-* -- true`.

## Decisions

1. **Implementation method: TDD.** Failing tests in `tests/test_argv.py`
   and `tests/test_sidecar_scripts.py` first; then `parse_agent_argv`.
   No real `opencode` in unit tests. **Alternative:** bash reorders argv
   into the old `srun --agent-* …` form — rejected; duplicates the flag
   table and would not teach `python3 -m agent_sidecar` the same grammar.

2. **Thin `sidecar.sh` stays exec.** Usage comment updates only.
   **Alternative:** getopts in the script — rejected (two parsers).

3. **Prefix + suffix flags.** Consume a leading `--agent-*` run, then
   require a launcher token, then the existing after-launcher loop.
   **Alternative:** drop suffix form — rejected; too much test churn.

4. **`--` optional, still forwarded.** `user_command_match` already
   falls back to the first non-dash token. Docs omit `--` for absolute
   paths. **Alternative:** require `--` always — rejected; that is the
   operator complaint.

5. **Acceptance is `测试.md`.** After unittest green, rsync to
   `/shared/agent-sidecar` and run healthy / abort / segfault exactly as
   documented (no in-srun `--agent-match`, no extra `--`).

## Risks / Trade-offs

- [`cli.main` special-cases argv[0] as `analy`/`report`] → Leading
  `--agent-*` only applies when the remaining command is a SLURM
  launcher; `sidecar-analy.sh` still injects `analy` first.
- [Prefix `--` before `srun` confused with SLURM `--`] → Ignore a lone
  `--` only before the launcher; do not document it.
- [Cluster OpenCode timeout] → Same 300s budget; do not set
  `AGENT_OPENCODE_FINAL_TIMEOUT=0`.

## Migration Plan

- Additive parser; old `srun --agent-*` still works.
- Rollback: revert `argv.py`; scripts stay thin exec.
- Public docs and demos switch to prefix form in this change.

## Open Questions

None.
