---
name: launch-fail
description: >-
  Diagnose MPI/user binary start failure: missing executable, ENOENT,
  execution_error with pid_count=0. Propose a corrected agent srun line.
  Use when the job never sampled any rank PIDs.
compatibility: opencode
---

# Launch failure (did not start)

Use when wrap `reason_code` is `execution_error` and `summary.pid_count` is 0,
or stderr/events mention `No such file or directory` / execve ENOENT.

The application **did not start**. This is not MPI abort, OOM, or IO imbalance.

## What to write

In `assist/job.json` `summary` (Simplified Chinese / 简体中文; 分条 numbered
list; keep the shell command as-is):

1. State that the executable was missing or not visible on the compute nodes.
2. On this cluster, binaries must live on NFS (`/shared/...`), not only on `mn`
   local disk (`/tmp` or a login-only path).
3. Give a **corrected** command, for example:

```bash
# compile onto NFS
mpicc -O2 -o /shared/agent-sidecar/examples/mpi_io_load \
  /shared/agent-sidecar/examples/mpi_io_load.c

python3 -m agent_sidecar srun --agent-output-dir /shared/agent-runs \
  -n3 -- \
  /shared/agent-sidecar/examples/mpi_io_load 60 /shared/mpi-io 30
```

Copy `suspected_reason` from `reason_code` (`execution_error`). `actions` stays
`[]`. Do not invent a different primary reason. Do not call `scancel`.
