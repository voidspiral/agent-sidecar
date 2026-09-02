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
agent srun --agent-profile=tools-only \
  --agent-skills=proc-monitor,slurm-tap,mpi-scan,node-diag \
  --agent-output-dir ./runs \
  -N 2 -n 4 -- ./app
```

Default `--agent-profile` is `tools-only` (deterministic node tools, no LLM).

| Flag | Meaning |
|------|---------|
| `--agent-profile` | `tools-only` (default), `node-assist`, `job-assist` |
| `--agent-skills` | comma-separated tools loaded by the node sidecar |
| `--agent-output-dir` | run directory parent (or set `AGENT_JOB_DIR`) |
| `--agent-node-llm` | opt-in node model; recorded as unsupported |
| `--agent-match` | override proc-monitor `--match` (default: user binary basename) |
| `--agent-interval` | sample interval in seconds (default `1.0`) |

Job-assist runs **once on the submit host** after `telemetry.json` is written.
It spawns OpenCode (`opencode run --dir <this repo>`). It does not POST
`/chat/completions` and does not run on compute nodes. OpenCode uses the
operator's existing Anthropic-compat env (`ANTHROPIC_*`). Those variables are
stripped from sidecar `srun`. There is **no HTTP fallback** if `opencode` is
missing.

```bash
# on mn; do not copy keys to compute nodes or git
# source the operator env file that sets ANTHROPIC_* for OpenCode

agent srun --agent-profile=job-assist \
  --agent-skills=proc-monitor,slurm-tap,mpi-scan,node-diag \
  --agent-output-dir ./runs \
  -N 2 -n 4 -- ./app
```

Missing OpenCode or runner errors are recorded in `collect_errors`
(`opencode_missing`, `opencode_timeout`, `opencode_failed`) and do not replace
the user command exit code. The model must not change `reason_code`.
`--agent-node-llm` still does not start a per-node model.

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
`AGENT_MPI_WORKDIR`). Provider keys stay on the login host
(operator env file), not on NFS.

Standing OpenCode instructions: `AGENTS.md` (same text as `agent.md`). Skills:
`.opencode/skills/`.

## Test cluster

Integration checks use four nodes: `mn`, `cn1`, `cn2`, `cn3`. Unit tests do
not require the cluster.

## Tests

```bash
python3 -m unittest discover -s tests
```
