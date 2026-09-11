---
name: mpi-segfault
description: >-
  Interpret SIGSEGV / signal 11 / fixture segfault evidence and
  assist/analysis.json from the mpi_segfault pack. Use when reason_code is
  mpi_segfault or analysis pack is mpi_segfault. Two-phase: without code_hits
  ask for --code; never invent file:line.
compatibility: opencode
---

# MPI segfault analysis

Use when wrap `reason_code` is `mpi_segfault`, or `assist/analysis.json` has
`pack=mpi_segfault`. Prefer the deterministic `analysis.json` excerpts over
re-reading every JSONL sample.

This is **not** `mpi_abort` (explicit Abort), **not** launch failure
(`execution_error` + `pid_count=0` → launch-fail), and **not** node OOM
(`node_local`).

## Artifacts

```text
{run_dir}/
  telemetry.json
  events/stderr.tail
  assist/analysis.json    # pack excerpts (fault_rank, signal, needs_source)
  assist/job.json         # Chinese numbered summary when written
  series/*.jsonl          # may be present if ranks ran before the crash
```

## How to interpret

1. Trust `reason_code` / `anomalies` / `analysis.json`. Do not scrape `/proc`.
2. Report fault rank and signal from analysis when present; say 未解析 if
   missing.
3. If `pid_count>0` / series brief exists, note that the job started then
   crashed — not ENOENT.
4. **Phase 1 (no source):** If `needs_source` is true or `code_hits` is empty,
   state that source-level location was **not** done. Ask the operator to
   re-run `ask_code_cmd` (or
   `sidecar-analy.sh --log <run_dir> --code /path/to/src`). **Do not invent
   `file:line`.** List only hypothesis-level causes (空指针 / 越界 / 未初始化).
5. **Phase 2 (authorized):** If `code_hits` is non-empty, cite
   path:lineno **only** from those hits and say they are under the
   user-authorized `--code` tree.
6. Suggest checking the faulting rank's pointer/bounds path and a corrected
   `agent srun` line with `--agent-match` and a shared binary path.

Copy `suspected_reason` from `reason_code` (`mpi_segfault`). `actions` stays
`[]`. Do not invent a different primary reason. Do not call `scancel` or
`scontrol`. Do not generate images.
