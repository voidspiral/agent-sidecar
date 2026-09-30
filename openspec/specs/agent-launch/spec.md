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
The CLI SHALL start an extra SLURM step with `--overlap --ntasks-per-node=1` and an explicit CPU/memory bound for the supervisor. On an `OverSubscribe=EXCLUSIVE` partition the user step SHALL also be launched with `srun --overlap` prepended, because SLURM will not create a second step on a node that already hosts one unless that step sets `--overlap`, even when CPUs remain. No other flag is inserted into the user argv. `--agent-overlap` remains accepted and does not change that default. If the overlap step is rejected or fails before the user command starts, the CLI SHALL stop the overlap step and fall back once to an exec-wrapper that forks a collector then execs the user binary in the same task. A node-assist agent MUST NOT be started once per rank in the exec-wrapper fallback.

#### Scenario: Default srun overlaps
- **WHEN** the user runs `agent srun` without `--agent-overlap`
- **THEN** the CLI starts one supervisor step with `--ntasks-per-node=1` and a memory bound before the user step, and the user step is `srun --overlap` followed by the user's original arguments

#### Scenario: Overlap supervisor on each node
- **WHEN** the allocation allows overlapping steps
- **THEN** the CLI starts one supervisor step with `--overlap --ntasks-per-node=1` and a memory bound before the user step, and the user step also passes `--overlap` so an exclusive partition accepts the second step

#### Scenario: Exec-wrapper fallback
- **WHEN** the overlap step fails because overlap is disabled
- **THEN** the CLI does not leave the overlap step running and retries once with exec-wrapper injection for tools only, recording the fallback in telemetry

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

### Requirement: Wrap runs deterministic analysis on non-ok
After `JobTelemetry` is written, when `reason_code` is not `ok` or
anomalies are non-empty, wrap SHALL invoke the deterministic analysis pack
path with LLM disabled. Missing OpenCode MUST NOT prevent
`assist/analysis.json` from being written.

#### Scenario: FINAL_TIMEOUT zero still gets analysis.json
- **WHEN** the user step exits non-zero with `mpi_abort` evidence and
  `AGENT_OPENCODE_FINAL_TIMEOUT` is `0`
- **THEN** wrap still writes `assist/analysis.json`

### Requirement: Wrap writes assist notes for ok jobs
After `JobTelemetry` is written, when `--agent-profile=job-assist` and
`reason_code` is `ok` with empty anomalies, wrap SHALL still write
`assist/job.json` with numbered Simplified Chinese suggestions from the
numeric summary. Missing OpenCode MUST NOT prevent that note.

#### Scenario: Healthy wrap still gets job.json
- **WHEN** the user step exits 0 with no tool anomalies and job-assist is on
- **THEN** wrap writes `assist/job.json` including a 建议 item without
  spawning OpenCode

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

### Requirement: NFS deploy includes eth-monitor on PYTHONPATH
`agent deploy` SHALL copy the eth-monitor source tree onto the shared prefix
alongside sidecar and mpi-monitor. Supervisor PYTHONPATH MUST include
`{sidecar}/src`, `AGENT_MPI_MONITOR_SRC` (default `/shared/mpi-monitor/src`),
and `AGENT_ETH_MONITOR_SRC` (default `/shared/eth-monitor/src`). Paths MUST
come from flags or env, not hardcoded user homes. Default skills SHALL
include `eth-monitor`.

#### Scenario: Deploy plans three trees
- **WHEN** `agent deploy --mpi-monitor MPI --eth-monitor ETH` runs
- **THEN** the plan copies eth-monitor to `{shared}/eth-monitor` and prints
  `AGENT_ETH_MONITOR_SRC` plus a PYTHONPATH containing all three `src` dirs

#### Scenario: Missing eth-monitor flag fails closed
- **WHEN** deploy is invoked without an eth-monitor tree
- **THEN** the CLI exits non-zero without copying

#### Scenario: Default skills include eth-monitor
- **WHEN** the user omits `--agent-skills`
- **THEN** supervisor skills include `eth-monitor` in addition to
  proc-monitor, mpi-scan, slurm-tap, and node-diag

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

### Requirement: sidecar.sh defaults to job-assist
When `sidecar.sh` launches a wrap command and the operator omitted
`--agent-profile`, the system SHALL default the profile to `job-assist`
(node tools plus submit-host OpenCode on tool artifacts). Explicit
`--agent-profile=tools-only` MUST skip wrap-time OpenCode. `sidecar-analy.sh`
is the source-authorized root-cause path (`--code`) and MUST NOT replace
the wrap-time job-assist note for a healthy job.

#### Scenario: sidecar.sh omit profile is job-assist
- **WHEN** `sidecar.sh srun -- ./app` runs with no `--agent-profile`
- **THEN** tool sidecars start and wrap-time OpenCode runs after telemetry

#### Scenario: sidecar.sh explicit tools-only
- **WHEN** `sidecar.sh srun --agent-profile=tools-only -- ./app` runs
- **THEN** wrap-time OpenCode is not launched

### Requirement: Sidecar flags precede the SLURM launcher
The wrap CLI SHALL accept known `--agent-*` flags before the launcher
word (`srun`, `sbatch`, or `salloc`) and MUST NOT forward those flags to
SLURM. `sidecar.sh [--agent-*] srun <slurm> <user>` is the preferred
operator form. The same leading-flag grammar MUST work for
`python3 -m agent_sidecar`. Known `--agent-*` immediately after the
launcher MUST remain accepted. An unrecognized `--agent-*` MUST still
fail closed before launching SLURM.

#### Scenario: Flags on sidecar.sh before srun
- **WHEN** the operator runs `sidecar.sh --agent-verbose srun -n 2 /path/app`
- **THEN** SLURM receives `-n 2 /path/app` (or equivalent) and does not
  receive `--agent-verbose`

#### Scenario: Module CLI leading flags
- **WHEN** the operator runs `python3 -m agent_sidecar --agent-profile=tools-only srun -n 1 ./app`
- **THEN** the profile is `tools-only` and SLURM passthrough is `-n 1 ./app`

#### Scenario: Trailing agent flags still work
- **WHEN** the operator runs `sidecar.sh srun --agent-verbose -n 1 hostname`
- **THEN** verbose is enabled and SLURM receives `-n 1 hostname`

#### Scenario: Unknown leading agent flag fails closed
- **WHEN** the operator runs `sidecar.sh --agent-nope srun -n 1 hostname`
- **THEN** the CLI exits non-zero with an error on stderr before launching SLURM

### Requirement: End-of-options dash-dash is optional
When the user command does not begin with `-`, the wrap CLI MUST accept
passthrough without a `--` separator. If `--` is present in the SLURM
passthrough, the CLI MUST forward it to SLURM. Public operator docs MUST
omit `--` for absolute-path example binaries.

#### Scenario: Absolute path without dash-dash
- **WHEN** the operator runs `sidecar.sh srun -n 2 /shared/agent-sidecar/examples/mpi_io_load 15 /shared/mpi-io 0`
- **THEN** SLURM passthrough is `-n 2` plus that binary and its arguments,
  and does not require `--`

#### Scenario: Operator-supplied dash-dash is forwarded
- **WHEN** the operator runs `sidecar.sh srun -n 1 -- python3 -c 'print(1)'`
- **THEN** SLURM receives the `--` token in passthrough

### Requirement: Wrap and analy route mpi_segfault pack
When wrap or `agent analy` sees tool/rollup `reason_code=mpi_segfault`,
deterministic analysis MUST select pack `mpi_segfault` (not `generic` /
`stub`). The segfault demo script MUST document expected
`reason_code=mpi_segfault` and `pid_count>0` after a short busy window.

#### Scenario: Pack selection for mpi_segfault
- **WHEN** telemetry `reason_code` is `mpi_segfault`
- **THEN** `select_pack` / `run_analysis` uses pack name `mpi_segfault`

#### Scenario: Demo documents expectations
- **WHEN** an operator runs the MPI segfault demo script
- **THEN** the script states expected `mpi_segfault` and sampled
  `pid_count>0`

### Requirement: Live submit-host watcher does not replace the PMI step
When job-assist starts a live OpenCode watcher, wrap MUST still launch the user
command as the PMI/PMIx task step. The watcher is a submit-host process (or
child of wrap), not a parent of every rank, and MUST NOT wrap the user step as
`bash -c 'opencode & exec app'`.

#### Scenario: Watcher is extra on the submit host
- **WHEN** job-assist wrap starts overlap supervisors and a live watcher
- **THEN** the user binary remains the SLURM PMI task and OpenCode is not in
  the user `srun` argv

#### Scenario: Watcher stops when wrap ends
- **WHEN** the wrapped user `srun` returns
- **THEN** the live watcher is stopped within the same bounded join as node
  sidecars
