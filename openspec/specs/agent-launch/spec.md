# agent-launch Specification

## Purpose

Defines how the `agent` CLI wraps SLURM launchers so a job-scoped sidecar starts with the allocation and the user `srun` remains the PMI task step.

## Requirements

### Requirement: Agent CLI wraps SLURM launchers
The CLI SHALL provide `agent srun`, `agent sbatch`, and `agent salloc` invocations that pass through SLURM arguments unchanged except for `--agent-*` flags, which the CLI MUST consume and MUST NOT forward to SLURM.

#### Scenario: Transparent srun passthrough
- **WHEN** the user runs `agent srun --agent-profile=tools-only -N 2 -n 8 -- ./app`
- **THEN** SLURM receives `-N 2 -n 8 -- ./app` (or equivalent) and does not receive `--agent-profile`

#### Scenario: Unknown agent flag fails closed
- **WHEN** the user passes an unrecognized `--agent-*` flag
- **THEN** the CLI SHALL exit non-zero with an error on stderr before launching SLURM

### Requirement: Sidecar injection does not replace the user PMI step
When wrapping `srun`, the CLI MUST start at most one supervisor per allocated node and MUST launch the user command as the PMI/PMIx task step. The CLI MUST NOT wrap every rank in a shell of the form `bash -c 'monitor & exec app'`.

#### Scenario: User srun remains the PMI step
- **WHEN** the user wraps an MPI `srun` that uses PMI or PMIx
- **THEN** the user binary is the SLURM task that inherits PMI environment, and supervisors are extra per-node processes rather than parents of every rank

#### Scenario: Forbidden per-rank bash wrapper
- **WHEN** injecting collectors for a multi-rank `srun`
- **THEN** the CLI MUST NOT emit `srun bash -c '… & exec …'` as the user step

### Requirement: Overlap step is the default injector with exec-wrapper fallback
The CLI SHALL prefer an extra SLURM step with `--overlap --ntasks-per-node=1` and an explicit CPU/memory bound for the supervisor. If overlap is rejected by the site, the CLI SHALL fall back to an exec-wrapper that forks a collector then execs the user binary in the same task. A node-assist agent MUST NOT be started once per rank in the exec-wrapper fallback.

#### Scenario: Overlap supervisor on each node
- **WHEN** the allocation allows overlapping steps
- **THEN** the CLI starts one supervisor step with `--ntasks-per-node=1` and a memory bound before the user step

#### Scenario: Exec-wrapper fallback
- **WHEN** the overlap step fails because overlap is disabled
- **THEN** the CLI retries once with exec-wrapper injection for tools only and records the fallback in telemetry

### Requirement: Sidecars follow job lifetime
Sidecar processes SHALL start before or with the user step and MUST terminate after the user step returns (bounded join). Sidecars MUST NOT remain as node daemons after the job ends.

#### Scenario: User step end stops sidecars
- **WHEN** the wrapped user `srun` returns
- **THEN** supervisors receive a stop signal, finish trailing samples, and exit within a bounded join timeout

#### Scenario: CLI exit code is the user command
- **WHEN** the user step exits with code N and sidecar collection has any non-fatal errors
- **THEN** the CLI exit code SHALL equal N, and collection errors SHALL be recorded in telemetry rather than replacing N

### Requirement: No hardcoded paths or invented hosts
Hosts, output directories, and SSH/srun fetch options MUST come from SLURM environment, CLI flags, or a config file. The implementation MUST NOT hardcode user home directories.

#### Scenario: Output dir from flags or job env
- **WHEN** `AGENT_JOB_DIR` or `--agent-output-dir` is set
- **THEN** telemetry and artifacts are written under that directory (or a run subdirectory of it)

#### Scenario: Missing output configuration
- **WHEN** neither a flag, config file, nor a documented default relative path is available
- **THEN** the CLI SHALL fail with a non-zero exit instead of writing under a hardcoded `/home/<user>/...` path

### Requirement: sbatch is a thin env wrapper
`agent sbatch` SHALL export profile, skills, and output-dir environment into the batch job and MUST NOT rewrite the batch script AST. Monitoring of inner `srun` lines REQUIRES those lines to use `agent srun` (or a later out-of-scope SPANK injector).

#### Scenario: sbatch exports agent context
- **WHEN** the user runs `agent sbatch --agent-profile=tools-only job.sh`
- **THEN** the batch job environment includes the profile and output settings and `job.sh` is submitted without textual rewrite of its `srun` lines

### Requirement: Submit-host live plot follows the user step
When live plot is enabled, wrap SHALL start a submit-host HTTP overlay server
before or with the user step and MUST stop it when the user step returns.
The server MUST NOT appear in the user `srun` argv and MUST NOT run on
compute nodes. `--agent-no-live-plot` MUST skip the server. Bind failure
MUST NOT replace the user command exit code.

#### Scenario: Live plot starts before the user command
- **WHEN** wrap runs with live plot enabled
- **THEN** the overlay server start happens before `run_user` and stop happens
  after the user step returns

#### Scenario: Quiet mode prints the plot URL
- **WHEN** quiet wrap starts the overlay server successfully
- **THEN** stderr or stdout includes a `live plot:` URL

#### Scenario: Bind failure is fail-soft
- **WHEN** the overlay port cannot be bound
- **THEN** the user command still runs and the CLI exit code remains the
  user command's code

### Requirement: agent analy subcommand
The CLI SHALL accept `agent analy` with required `--run-dir` and optional
`--code` and `--llm`. The subcommand MUST run on the submit/login host
only, MUST NOT start overlap supervisors, and MUST exit non-zero on
missing run directory.

#### Scenario: analy requires run-dir
- **WHEN** the user runs `agent analy` without `--run-dir`
- **THEN** the CLI exits non-zero with an error on stderr

#### Scenario: analy does not start sidecars
- **WHEN** `agent analy --run-dir DIR` runs successfully
- **THEN** no compute-node supervisor process is started for that
  invocation

### Requirement: Wrap runs deterministic analysis on non-ok
After `JobTelemetry` is written, when `reason_code` is not `ok` or
anomalies are non-empty, wrap SHALL invoke the deterministic analysis pack
path with LLM disabled. Missing OpenCode MUST NOT prevent
`assist/analysis.json` from being written.

#### Scenario: FINAL_TIMEOUT zero still gets analysis.json
- **WHEN** the user step exits non-zero with `mpi_abort` evidence and
  `AGENT_OPENCODE_FINAL_TIMEOUT` is `0`
- **THEN** wrap still writes `assist/analysis.json`

### Requirement: Stderr tail flushes during the user step
While capturing user stdio into `events/stderr.tail`, wrap SHALL
periodically flush the ring buffer to disk during the user step so abort
text can appear before process exit. The final flush on exit MUST still
occur.

#### Scenario: Abort text visible before exit flush
- **WHEN** the user command prints `MPI_Abort` and continues briefly before
  exiting
- **THEN** `events/stderr.tail` contains that text after a flush interval
  without waiting solely for process termination
