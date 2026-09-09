---
name: mpi-abort
description: >-
  Interpret MPI_Abort / PMIx abort evidence and assist/analysis.json from the
  mpi_abort pack. Use when reason_code is mpi_abort or analysis pack is
  mpi_abort.
compatibility: opencode
---

# MPI abort analysis

Use when wrap `reason_code` is `mpi_abort`, or `assist/analysis.json` has
`pack=mpi_abort`. Prefer the deterministic `analysis.json` excerpts over
re-reading every JSONL sample.

This is **not** launch failure (`execution_error` + `pid_count=0` →
launch-fail) and **not** node OOM (`node_local`).

## Artifacts

```text
{run_dir}/
  telemetry.json
  events/stderr.tail
  assist/analysis.json    # pack excerpts (abort_rank, errorcode, series brief)
  assist/job.json         # Chinese numbered summary when written
  series/*.jsonl          # may be present if ranks ran before abort
```

## How to interpret

1. Trust `reason_code` / `anomalies` / `analysis.json`. Do not scrape `/proc`.
2. Report abort rank and errorcode from analysis when present; say 未解析 if
   missing.
3. If `pid_count>0` / series brief exists, note that the job started then
   aborted — not ENOENT.
4. If `--code` produced `code_hits`, cite path:lineno only from those hits.
5. Suggest checking the aborting rank's error path and a corrected
   `agent srun` line with `--agent-match` and a shared binary path.

Copy `suspected_reason` from `reason_code` (`mpi_abort`). `actions` stays
`[]`. Do not invent a different primary reason. Do not call `scancel` or
`scontrol`. Do not generate images.
