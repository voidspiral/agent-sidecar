## ADDED Requirements

### Requirement: Login-host sidecar.sh and sidecar-analy.sh
The repository SHALL ship executable login-host scripts `scripts/sidecar.sh`
and `scripts/sidecar-analy.sh`. Each MUST set `PYTHONPATH` to the tree's
`src/` directory and MUST exec `python3 -m agent_sidecar` without rewriting
SLURM argv. `sidecar.sh` MUST prefix the remaining argv as a launcher
subcommand (`srun`, `sbatch`, or `salloc`). `sidecar-analy.sh` MUST invoke
the `analy` subcommand. Neither script MUST start compute-node sidecars by
itself beyond what the wrapped CLI already does for `srun`. Deploy output
MUST print the `/shared/agent-sidecar/scripts/` paths for both scripts.

#### Scenario: sidecar.sh wraps srun
- **WHEN** the operator runs `sidecar.sh srun -N 2 -n 4 -- ./app`
- **THEN** the CLI receives `srun` plus the passthrough SLURM/user argv
  and does not receive the script path as a SLURM argument

#### Scenario: sidecar-analy.sh wraps analy
- **WHEN** the operator runs `sidecar-analy.sh --log DIR --code PATH`
- **THEN** the CLI runs `analy` with those flags on the submit host and
  starts no additional overlap supervisor beyond the wrapped command

### Requirement: sidecar.sh defaults to tools-only
When `sidecar.sh` launches a wrap command and the operator omitted
`--agent-profile`, the system SHALL default the profile to `tools-only`.
An explicit `--agent-profile` on the command line MUST win. Invoking
`agent srun` / `python3 -m agent_sidecar srun` without `sidecar.sh` MUST
NOT change omitted-profile behavior in this change.

#### Scenario: sidecar.sh omit profile is tools-only
- **WHEN** `sidecar.sh srun -- ./app` runs with no `--agent-profile`
- **THEN** only tool sidecars start and wrap-time OpenCode is not launched

#### Scenario: sidecar.sh explicit job-assist
- **WHEN** `sidecar.sh srun --agent-profile=job-assist -- ./app` runs
- **THEN** the job-assist profile is used

#### Scenario: module srun omit profile unchanged
- **WHEN** `python3 -m agent_sidecar srun -- ./app` runs without
  `--agent-profile` and without the sidecar.sh entry env
- **THEN** omitted-profile behavior remains the pre-change default

## MODIFIED Requirements

### Requirement: agent analy subcommand
The CLI SHALL accept `agent analy` with required `--log DIR` or
`--run-dir DIR` (aliases for the same sidecar run directory) and optional
`--code`, `--llm`, and `--no-llm`. If both `--log` and `--run-dir` are
set to different paths, the CLI MUST exit non-zero. The subcommand MUST
run on the submit/login host only, MUST NOT start overlap supervisors,
and MUST exit non-zero on a missing run directory.

#### Scenario: analy requires log or run-dir
- **WHEN** the user runs `agent analy` without `--log` and without
  `--run-dir`
- **THEN** the CLI exits non-zero with an error on stderr

#### Scenario: analy --log is the run directory
- **WHEN** the user runs `agent analy --log DIR` and `DIR` is a sidecar
  run directory
- **THEN** analysis uses that directory as the run tree

#### Scenario: analy does not start sidecars
- **WHEN** `agent analy --log DIR` or `agent analy --run-dir DIR` runs
  successfully
- **THEN** no compute-node supervisor process is started for that
  invocation
