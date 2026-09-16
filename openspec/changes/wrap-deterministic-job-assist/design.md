## Context

`run_job_assist` currently unlinks any pack `assist/job.json` and always
spawns `opencode run` after wrap unless `AGENT_OPENCODE_FINAL_TIMEOUT=0`.
Healthy jobs have no live note, so every successful MPI wrap pays a full
OpenCode session. Pack notes are discarded even when they already contain
Chinese advice.

## Goals / Non-Goals

**Goals:**

- Healthy jobs (`reason_code=ok`, no anomalies) still get `assist/job.json`
  with numbered 简体中文 items: conclusion, sampled metrics, anomalies (none),
  and **suggestions** derived from CPU/RSS/IO/ethernet / pid counts.
- Default wrap wall clock does not wait on OpenCode.
- Pack-written notes survive wrap.
- TDD (failing unittest first).

**Non-Goals:**

- ClusterHelm control plane.
- Changing live OpenCode-on-anomaly or `agent analy --llm`.
- Inferring uncollected Lustre OST counters.

## Decisions

1. **Default wrap path is deterministic.** `AGENT_OPENCODE_FINAL_TIMEOUT` unset
   or `0` (or `timeout<=0`) skips OpenCode and writes or keeps a note.
   A **positive** `AGENT_OPENCODE_FINAL_TIMEOUT` restores today’s unlink +
   `run_opencode_assist` escape hatch.
2. **Healthy suggestions are a first-class pack-like module**
   (`resource_hints.chinese_summary`), not an empty stub. Heuristics read only
   `JobTelemetry.summary` / `anomalies` / `reason_code` (no JSONL bodies).
   Always emit item `4. 建议：…`. Rules: unmatched pids; low vs high
   `cpu_peak`; IO-heavy vs CPU; ethernet peaks are host NIC rates not MPI
   bytes; if none fire, still suggest keeping current `srun`/`--interval`.
3. **Precedence:** live.json summary → promote; else existing job.json
   summary (pack) → keep and list on telemetry; else resource hints.
4. **`agent analy --llm` unchanged:** may unlink and spawn OpenCode.

## Risks / Trade-offs

- Heuristic suggestions are shallower than a model. Accepted: operators
  asked for speed plus monitoring-based advice; `analy --llm` remains.
- Stub packs (generic “no dedicated pack”) stay if wrap already wrote them;
  not rewritten by hints. Accepted for this change.
- `timeout=0` previously wrote no `job.json`; now writes hints so healthy
  jobs still have 建议.

## Migration Plan

No on-disk schema change. Operators who relied on wrap OpenCode set
`AGENT_OPENCODE_FINAL_TIMEOUT` to a positive budget.

## Open Questions

None.
