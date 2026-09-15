---
name: node-diag
description: >-
  Interpret compute-node OOM and filesystem hang evidence from node-diag
  (dmesg/kmsg + job cgroup). Use when reason_code is node_local, or
  events/node-diag.txt shows oom_pids, oom_kill, or fs_hang_lines.
compatibility: opencode
---

# Node diagnostics (this sidecar)

`node-diag` runs **on each compute node** inside the overlap supervisor. It
reads kernel OOM traces (`dmesg` or `/dev/kmsg`) and the SLURM job cgroup
(`cgroup.procs`, cgroup v2 `memory.events` or v1 `memory.oom_control`). It
refreshes on supervisor stop so an OOM during the user step is visible.

This is **not** process RSS (`proc-monitor`) and **not** SLURM
`OUT_OF_MEMORY` accounting (`slurm-tap` → `slurm_oom`).

## When to use

- `telemetry.json` `reason_code` is `node_local`
- `events/node-diag.txt` has `oom_pids=[...]` (not empty), `oom_kill>=1`,
  or `fs_hang_lines>=1`
- Job died with a kill/OOM story but `slurm.json` is still RUNNING/COMPLETED

**Not** for start failure (`execution_error` + `pid_count=0` → launch-fail)
or MPI abort text (`mpi-scan`).

## Artifacts

```text
{run_dir}/
  events/node-diag.txt      # oom_pids, cgroup_pids, oom_kill, fs_hang_lines
  events/{host}_markers.jsonl  # first-seen node_local for chart overlays
  events/node_diag.err      # optional; dmesg/cgroup unreadable
```

`oom_pids` are job-scoped: live collect ignores historical `Killed process`
lines whose PIDs are not in this job cgroup. `oom_kill` is the cgroup counter
(delta vs start). Empty `oom_pids=[]` with `oom_kill=0` is not an anomaly.

Permission denied on `dmesg`/`/dev/kmsg` is a collect error, not a job fault.

## How to interpret

1. Trust `reason_code` / `anomalies`. Do not scrape `/proc` or re-run `dmesg`.
   Do **not** read PNG pixels; `node_local` chart time comes from
   `events/{host}_markers.jsonl` when present.
2. If `oom_pids` or `oom_kill` is set: the node OOM killer (or memcg) hit a
   task in this job. Suggest a higher `--mem` / cgroup limit, or less
   per-rank RSS. Keep `suspected_reason` as `node_local`.
3. If `slurm-tap` also has `slurm_oom`, say both: accounting OOM and node
   killer evidence. Do not replace `reason_code`.
4. If `fs_hang_lines>=1`: NFS or hung-task signal. Check the shared path
   (`/shared`, `AGENT_MPI_WORKDIR`), not CPU/IO imbalance.
5. Missing `node-diag.txt` or only `node_diag.err`: collection failed; do not
   invent an OOM.

Copy `suspected_reason` from `reason_code`. `actions` stays `[]`.
Do not call `scancel` or `scontrol`.
