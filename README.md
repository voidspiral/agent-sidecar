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
| `--agent-llm-base-url` | override `AGENT_LLM_BASE_URL` (job-assist) |
| `--agent-llm-model` | override `AGENT_LLM_MODEL` (job-assist) |

Job-assist runs **once on the submit host** after `telemetry.json` is written.
It does not run on compute nodes. Configure the OpenAI-compatible endpoint
with environment variables (API key is env-only, never a CLI flag):

```bash
export AGENT_LLM_BASE_URL=https://api.example.com/v1
export AGENT_LLM_API_KEY=...   # do not commit
export AGENT_LLM_MODEL=your-model
# optional: AGENT_LLM_TIMEOUT=30

agent srun --agent-profile=job-assist \
  --agent-skills=proc-monitor,slurm-tap,mpi-scan,node-diag \
  --agent-output-dir ./runs \
  -N 2 -n 4 -- ./app
```

Missing credentials or provider errors are recorded in `collect_errors` and
do not replace the user command exit code. The model must not change
`reason_code`. `--agent-node-llm` still does not start a per-node model.

A ~60s MPI + IO sample lives in `examples/mpi_io_load.c`. On the login host:

```bash
bash scripts/demo_job_assist_mpi.sh
```

## Test cluster

Integration checks use four nodes: `mn`, `cn1`, `cn2`, `cn3`. Unit tests do
not require the cluster.

## Tests

```bash
python3 -m unittest discover -s tests
```
