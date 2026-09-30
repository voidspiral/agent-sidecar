## Why

Operators currently wrap jobs with `python3 -m agent_sidecar srun` and
re-analyze with `agent analy --run-dir` plus opt-in `--llm`. HPC users
need two login-host shell entries that match how they already launch
work: run the job, then later authorize source and interpret with a
model by default.

## What Changes

- Add `scripts/sidecar.sh` wrapping `srun`/`sbatch`/`salloc`. Omitted
  `--agent-profile` stays `job-assist`: node tools plus submit-host OpenCode
  on tool artifacts after every wrap (including healthy jobs).
  `--agent-profile=tools-only` remains the opt-out.
- Add `scripts/sidecar-analy.sh` wrapping `agent analy`.
- **BREAKING** for `agent analy`: OpenCode is on by default. `--no-llm`
  restores the deterministic-only path. `--llm` remains accepted.
- `agent analy` accepts `--log DIR` as the public name for the sidecar
  run directory. `--run-dir` stays as a compatible alias. One of the two
  is required; conflicting values fail closed.
- Phase-1 `ask_code_cmd` and quiet-report next-step text point at
  `sidecar-analy.sh --log … --code …`.
- Deploy import-check footer prints the two script paths on `/shared`.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `agent-launch`: Login-host `sidecar.sh` / `sidecar-analy.sh`; wrap
  defaults to `job-assist`; `analy` accepts `--log` or `--run-dir`.
- `job-analysis`: `agent analy` defaults to OpenCode; `--no-llm` is the
  deterministic path; `ask_code_cmd` cites `sidecar-analy.sh --log`.

## Impact

- Scripts: `scripts/sidecar.sh`, `scripts/sidecar-analy.sh`
- CLI: [`src/agent_sidecar/cli.py`](src/agent_sidecar/cli.py)
- Profile defaults: [`src/agent_sidecar/argv.py`](src/agent_sidecar/argv.py)
- Packs / report / deploy: `analysis/mpi_abort.py`, `report.py`, `deploy.py`
- README, demos, OpenCode skills, job-assist standing docs if they cite
  `analy --run-dir`
- Tests under `tests/` (TDD, no real `opencode` exec)

## Non-goals

- ClusterHelm control-plane integration (Master/Slave, workflow_runner,
  partition_report, SPANK, auto `scancel`).
- Ingesting raw SLURM `.out` or arbitrary application logs as `--log`.
- Wrap-time OpenCode is the default for `sidecar.sh` (job-assist). Source
  citation still requires `sidecar-analy.sh --code`.
- Changing omitted `--agent-profile` behavior for
  `python3 -m agent_sidecar srun` / `agent srun`.
- Compute-node LLM, automatic remediate, or inventing `reason_code`.
