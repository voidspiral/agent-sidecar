# Agent sidecar job-assist

This repository is a standalone HPC SLURM job-lifecycle sidecar. It is **not**
ClusterHelm. Do not use Master/Slave, `workflow_runner`, `partition_report`,
or `run-slave.sh`.

## Role

You run **once on the submit/login host** after `telemetry.json` exists.
Compute-node sidecars are deterministic tools only (`proc-monitor`, `mpi-scan`,
`slurm-tap`, `node-diag`). Do not scrape `/proc`. Do not start OpenCode on
compute nodes. Do not call `scancel` or `scontrol`. Do not overwrite
`reason_code`.

## Input

Read only the JSON contract in the prompt (and `telemetry.json` if you need
to confirm paths):

- `summary` — numeric CPU/RSS/IO, `host_count`, `pid_count`, `exit_code`
- `anomalies` — tool events
- `reason_code` — authoritative tool/rollup code
- `evidence_paths` — JSONL and PNG **paths**, not file bodies

Do not embed every series sample in your note.

## Charts

PNG files under `charts/` are produced locally (matplotlib / mpi-monitor plot).
The chat model is text-only. **Do not generate or request images.** Interpret
paths and the numeric summary instead.

## Output

Write `assist/job.json` under `run_dir`:

```json
{
  "host": "submit",
  "summary": "<interpretation; on launch failure include a corrected agent srun line>",
  "suspected_reason": "<copy telemetry.reason_code>",
  "evidence_paths": ["<from the contract>"],
  "confidence": null,
  "actions": []
}
```

`actions` MUST be `[]`. `suspected_reason` MUST copy `reason_code`.

## Launch failure

If `reason_code` is `execution_error` and `pid_count` is 0, the user binary
likely never started (missing path, ENOENT, not on NFS). Say that clearly and
propose a corrected `agent srun` line: compile to a shared path such as
`/shared/agent-sidecar/examples/mpi_io_load` and pass that path after `--`.

Load skills under `.opencode/skills/` (mpi-monitor timeseries, launch-fail).
