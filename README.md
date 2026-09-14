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

Without `pip install`, use the login-host scripts (they set `PYTHONPATH`):

```bash
bash /shared/agent-sidecar/scripts/sidecar.sh srun -N 2 -n 4 ./app
bash /shared/agent-sidecar/scripts/sidecar.sh --agent-verbose srun -N 2 -n 4 ./app
bash /shared/agent-sidecar/scripts/sidecar-analy.sh --log /shared/agent-runs/<run_id> --code /path/to/src
```

`sidecar.sh` wraps the user `srun`, collects with node tools, and runs
job-assist OpenCode on those artifacts (same default as `agent srun`).
Sidecar flags (`--agent-*`) go **before** `srun`. `--` is optional when the
user command is not option-shaped. `--agent-profile=tools-only` skips the
wrap-time model.
`sidecar-analy.sh` is the later **source-authorized** pass: `--log` is the
run directory, `--code` is the tree the operator allows the model to cite.
Pass `--no-llm` for the deterministic pack only. The module form
`python3 -m agent_sidecar …` remains available for advanced use.

## Wrap a job

`--agent-*` flags are consumed by this CLI and are **not** forwarded to SLURM.
Put them on `sidecar.sh` (or `python3 -m agent_sidecar`) **before** `srun`.

```bash
sidecar.sh srun -N 2 -n 4 ./app
python3 -m agent_sidecar --agent-profile=tools-only srun -N 2 -n 4 ./app
```

Default `--agent-profile` is `job-assist`. `--agent-skills` defaults to
`proc-monitor,mpi-scan,slurm-tap,node-diag,eth-monitor`. If `/shared` exists, the output directory defaults to
`/shared/agent-runs`. Logging defaults to quiet (key steps + final report).
`--agent-verbose` prints the full launch trace. `--agent-profile=tools-only`
skips OpenCode.

| Flag | Meaning |
|------|---------|
| `--agent-profile` | `job-assist` (default), `tools-only` (no OpenCode), `node-assist` |
| `--agent-skills` | comma-separated tools loaded by the node sidecar |
| `--agent-output-dir` | run directory parent (or set `AGENT_JOB_DIR`) |
| `--agent-verbose` | print overlap sidecar / user-step launch trace and raw telemetry |
| `--agent-quiet` | key steps only, then a compact `report.txt` (header, job-assist, metrics, hosts, evidence counts). Also `AGENT_QUIET=1` |
| `--agent-node-llm` | opt-in node model; recorded as unsupported |
| `--agent-match` | override proc-monitor `--match` (default: user binary basename) |
| `--agent-interval` | sample interval in seconds (default `1.0`) |
| `--agent-live-plot` / `--agent-no-live-plot` | submit-host overlay HTTP (default on). `AGENT_LIVE_PLOT=0` opts out; `AGENT_LIVE_PLOT_PORT` sets the port (default `8765`) |

Job-assist runs **on the submit host**: a live OpenCode watcher runs **only
when tool anomalies appear** in `events/` (MPI abort, SLURM failure/OOM,
node-diag). Healthy CPU/RSS/IO series changes do not spawn OpenCode. It does not POST `/chat/completions`, does not source
a provider env file, and does not run on compute nodes. OpenCode uses its own
login-host config. Provider keys that happen to be in the process environment
are stripped from sidecar `srun`. There is **no HTTP fallback** if `opencode`
is missing.

```bash
# on mn; OpenCode credentials stay in OpenCode's own config, not this repo

agent srun -N 2 -n 4 ./app
```

`--agent-profile=tools-only` skips OpenCode. Missing OpenCode or runner errors are recorded in `collect_errors`
(`opencode_missing`, `opencode_timeout`, `opencode_failed`) and do not replace
the user command exit code. The model must not change `reason_code`.
`--agent-node-llm` still does not start a per-node model.

Optional: set `AGENT_OPENCODE_MODEL` (`provider/model`) to pin the model.
Live OpenCode timeout defaults to 300s (`AGENT_OPENCODE_TIMEOUT`). Wrap
cancels live OpenCode when the user step ends and promotes `assist/live.json`
to `assist/job.json` if a live summary exists. Otherwise it runs a post-job
OpenCode (same default budget unless `AGENT_OPENCODE_FINAL_TIMEOUT` is set).
Set `AGENT_OPENCODE_FINAL_TIMEOUT=0` to skip the post-job model.

`proc-monitor` imports `mpi_monitor.collect.collect_loop`. `eth-monitor`
imports `eth_monitor.collect.collect_loop`. Deploy **all three** trees onto
NFS so every compute node can import them. Default Python paths are
`/shared/mpi-monitor/src` (`AGENT_MPI_MONITOR_SRC`) and
`/shared/eth-monitor/src` (`AGENT_ETH_MONITOR_SRC`).

```bash
# on mn — mpi-monitor then eth-monitor (repo root or src/)
bash scripts/deploy_shared.sh /path/to/mpi-monitor /path/to/eth-monitor
# dry-run
bash scripts/deploy_shared.sh --dry-run /path/to/mpi-monitor /path/to/eth-monitor
# equivalent
python3 -m agent_sidecar deploy --mpi-monitor /path/to/mpi-monitor --eth-monitor /path/to/eth-monitor
```

The tool rsyncs this repo to `/shared/agent-sidecar`, mpi-monitor to
`/shared/mpi-monitor`, and eth-monitor to `/shared/eth-monitor`, then prints
`AGENT_MPI_MONITOR_SRC`, `AGENT_ETH_MONITOR_SRC`, and `PYTHONPATH`.
`agent srun` injects those paths for the overlap supervisor; you do not need
to export `PYTHONPATH` for wrapped jobs. Missing mpi-monitor or eth-monitor
is fail-soft (`events/mpi_monitor_import.err`, `events/eth_monitor_import.err`).

Wrap writes optional PNG under `charts/` when matplotlib is installed (one file
per pid × metric). While the job runs, the submit host also serves a live
overlay page (all processes of one metric on one chart, legend by rank or
`host pid`). Quiet wrap prints `[agent] live plot: http://127.0.0.1:8765`.
From a laptop: `ssh -L 8765:127.0.0.1:8765 mn`. Replay a finished run:

```bash
python3 -m agent_sidecar serve --run-dir /shared/agent-runs/<run_id>
```

`--agent-no-live-plot` or `AGENT_LIVE_PLOT=0` skips the server. Bind failure is
fail-soft (`collect_errors.live_plot`) and does not change the user exit code.

An MPI sample lives in `examples/mpi_io_load.c`: ~60s NFS write/fsync/read
per rank, then a 30s local CPU burn (`mpi_io_load [io_seconds] [work_dir]
[cpu_seconds]`; pass `0` as the third argument to skip CPU). The test cluster
exports NFS at `/shared` (`mn:/shared`). Place the tree, binary, IO scratch,
and run output there so every node sees the same files:

```bash
# on mn
bash scripts/deploy_shared.sh /path/to/mpi-monitor /path/to/eth-monitor
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
Chinese: `.opencode/AGENTS.zh.md`. OpenCode skills: `.opencode/skills/`
(index: [.opencode/skills.md](.opencode/skills.md)).

## Implemented skills

Two layers. `--agent-skills` selects deterministic compute-node tools.
`.opencode/skills/` are submit-host OpenCode skills that interpret those
artifacts.

### Node tools (`--agent-skills`)

Default is all five node tools:
`proc-monitor,mpi-scan,slurm-tap,node-diag,eth-monitor`. Comma-separate to override.

| Name | Role | Artifacts |
|------|------|-----------|
| `proc-monitor` | Sample matched user PIDs for CPU/RSS/IO via mpi-monitor `collect_loop` | `series/{host}_pid{pid}.jsonl`; `charts/*.png` when matplotlib is present |
| `eth-monitor` | Sample host ethernet rx/tx via eth-monitor `collect_loop` | `series/{host}_net.jsonl`; ethernet PNG when matplotlib is present |
| `mpi-scan` | Scan MPI/launcher stderr for abort patterns | `events/stderr.tail` |
| `slurm-tap` | Parse scontrol/sstat/sacct job state | `events/slurm.json` |
| `node-diag` | Collect local OOM / cgroup / hang on the compute node; refresh on `stop` | `events/node-diag.txt` |

Launchers (`srun`, `mpirun`, `orted`, …) are never sampled by `proc-monitor`.

`node-diag` reads `dmesg` or `/dev/kmsg`, plus the job cgroup's
`cgroup.procs` and `memory.events` (v1: `memory.oom_control`). It emits
`node_local` only for job-scoped OOM (cgroup PID intersection or an
`oom_kill` increase) or a hang-only snapshot. Historical `Killed process`
lines from other jobs are ignored. Read failures write
`events/node_diag.err` and do not change the user exit code.

### OpenCode skills (`.opencode/skills/`)

Loaded by job-assist on the login host. They do not run a model on compute
nodes. Full index: [.opencode/skills.md](.opencode/skills.md).

| Skill | When to use |
|-------|-------------|
| [mpi-monitor](.opencode/skills/mpi-monitor/SKILL.md) | Interpret CPU/RSS/IO from `series/` and `charts/` paths; empty series vs start failure |
| [eth-monitor](.opencode/skills/eth-monitor/SKILL.md) | Interpret host ethernet rx/tx from `series/{host}_net.jsonl`; not MPI traffic |
| [launch-fail](.opencode/skills/launch-fail/SKILL.md) | `reason_code=execution_error` and `pid_count=0` (ENOENT / binary not on NFS) |
| [mpi-abort](.opencode/skills/mpi-abort/SKILL.md) | `reason_code=mpi_abort` or `assist/analysis.json` pack `mpi_abort` |
| [mpi-segfault](.opencode/skills/mpi-segfault/SKILL.md) | `reason_code=mpi_segfault` or `assist/analysis.json` pack `mpi_segfault` |
| [node-diag](.opencode/skills/node-diag/SKILL.md) | `reason_code=node_local` or `events/node-diag.txt` shows in-job OOM / cgroup `oom_kill` / NFS hang |

Offline analysis is **two phases** and defaults to OpenCode:
(1) without `--code` — symptoms + ask for source; (2) with `--code` — cite
authorized path hits only. `--no-llm` keeps the deterministic pack.
`--run-dir` is an alias of `--log`.

```bash
# phase 1 — no source tree (LLM default)
bash /shared/agent-sidecar/scripts/sidecar-analy.sh --log /shared/agent-runs/<run_id>
# phase 1 deterministic only
bash /shared/agent-sidecar/scripts/sidecar-analy.sh --log DIR --no-llm
# phase 2 — operator-authorized source (LLM default)
bash /shared/agent-sidecar/scripts/sidecar-analy.sh --log DIR --code /path/to/src
```

MPI abort fixture demo (expects `reason_code=mpi_abort`, `pid_count>0`,
`assist/analysis.json` with `needs_source=true` until `--code`):

```bash
bash /shared/agent-sidecar/scripts/demo_mpi_abort.sh
```

MPI segfault fixture demo (expects `reason_code=mpi_segfault`, `pid_count>0`,
`needs_source=true` until `--code`):

```bash
bash /shared/agent-sidecar/scripts/demo_mpi_segfault.sh
```

## Test cluster

Integration checks use four nodes: `mn`, `cn1`, `cn2`, `cn3`. Unit tests do
not require the cluster.

## Tests

```bash
python3 -m unittest discover -s tests
```
