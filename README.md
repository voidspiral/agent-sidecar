# agent-sidecar

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
| `--agent-node-llm` | opt-in node model; phase 1 records unsupported |

## Test cluster

Integration checks use four nodes: `mn`, `cn1`, `cn2`, `cn3`. Unit tests do
not require the cluster.

## Tests

```bash
python3 -m unittest discover -s tests
```
