# agent-sidecar

中文说明见 [README.zh.md](README.zh.md)。

Job-lifecycle sidecar for SLURM. Wrap `srun` so a per-node sidecar starts with
the allocation, samples process CPU/RSS/IO, classifies SLURM/MPI/node faults,
and writes `JobTelemetry`. Sidecars stop when the job ends.

This is not ClusterHelm. Master/Slave, `workflow_runner`, and
`partition_report` are out of scope.

## Install

```bash
pip install -e .
# optional PNG charts
pip install -e ".[plot]"
```

Python 3.10+. Output paths come from `--agent-output-dir`, `AGENT_JOB_DIR`,
or a relative run directory. Do not hardcode `/home/<user>/...`.

## Wrap a job

`--agent-*` flags are consumed by this CLI and are **not** forwarded to SLURM.

```bash
agent srun -N 2 -n 4 -- ./app
```

Default `--agent-profile` is `job-assist`. `--agent-skills` defaults to
`proc-monitor`. If `/shared` exists, the output directory defaults to
`/shared/agent-runs`. Logging defaults to quiet (key steps + final report).
`--agent-verbose` prints the full launch trace. `--agent-profile=tools-only`
skips OpenCode.

| Flag | Meaning |
|------|---------|
| `--agent-profile` | `job-assist` (default), `tools-only` (no OpenCode), `node-assist` |
| `--agent-skills` | comma-separated tools loaded by the node sidecar |
| `--agent-output-dir` | run directory parent (or set `AGENT_JOB_DIR`) |
| `--agent-verbose` | print overlap sidecar / user-step launch trace and raw telemetry |
| `--agent-quiet` | key steps only, then a final `report.txt` (summary + artifacts). Also `AGENT_QUIET=1` |
| `--agent-node-llm` | opt-in node model; recorded as unsupported |
| `--agent-match` | override proc-monitor `--match` (default: user binary basename) |
| `--agent-interval` | sample interval in seconds (default `1.0`) |

Job-assist runs **on the submit host**: a live OpenCode watcher ticks on
artifact snapshots while the user step runs, then one final `opencode run`
after `telemetry.json`. It does not POST `/chat/completions`, does not source
a provider env file, and does not run on compute nodes. OpenCode uses its own
login-host config. Provider keys that happen to be in the process environment
are stripped from sidecar `srun`. There is **no HTTP fallback** if `opencode`
is missing.

```bash
# on mn; OpenCode credentials stay in OpenCode's own config, not this repo

agent srun -N 2 -n 4 -- ./app
```

`--agent-profile=tools-only` skips OpenCode. Missing OpenCode or runner errors are recorded in `collect_errors`
(`opencode_missing`, `opencode_timeout`, `opencode_failed`) and do not replace
the user command exit code. The model must not change `reason_code`.
`--agent-node-llm` still does not start a per-node model.

Optional: set `AGENT_OPENCODE_MODEL` (`provider/model`) to pin the model.

Set `AGENT_MPI_MONITOR_SRC` if mpi-monitor is not at `/shared/mpi-monitor/src`.
Wrap writes optional PNG under `charts/` when matplotlib is installed.

A ~60s MPI + IO sample lives in `examples/mpi_io_load.c`. The test cluster
exports NFS at `/shared` (`mn:/shared`). Place the tree, binary, IO scratch,
and run output there so every node sees the same files:

```bash
# on mn
rsync -az ./ /shared/agent-sidecar/
rsync -az /path/to/mpi-monitor/ /shared/mpi-monitor/
bash /shared/agent-sidecar/scripts/demo_job_assist_mpi.sh \
  /shared/agent-sidecar /shared/agent-runs
```

A missing-binary fixture for OpenCode diagnosis:

```bash
bash /shared/agent-sidecar/scripts/demo_opencode_launch_fail.sh
```

The sample writes per-rank files under `/shared/mpi-io` (override with
`AGENT_MPI_WORKDIR`). OpenCode credentials stay in OpenCode's login-host
config, not in this repo and not on NFS.

Standing instructions live in tool directories (OpenCode is the job-assist
LLM; Cursor is local debug): `.opencode/AGENTS.md`,
`.opencode/agent/job-assist.md`, `.cursor/rules/job-assist.mdc`.
Chinese: `.opencode/AGENTS.zh.md`. Skills: `.opencode/skills/`.

## Test cluster

Integration checks use four nodes: `mn`, `cn1`, `cn2`, `cn3`. Unit tests do
not require the cluster.

## Tests

```bash
python3 -m unittest discover -s tests
```
