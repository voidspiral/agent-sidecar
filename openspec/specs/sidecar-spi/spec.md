# sidecar-spi Specification

## Purpose

Defines the per-node supervisor and the deterministic tool plugin contract used to collect process, SLURM, MPI, and node evidence without putting an LLM on the sampling path.

## Requirements

### Requirement: One supervisor per node per job
For a given `SLURM_JOB_ID` and hostname, the system SHALL run at most one supervisor process. The supervisor loads the requested tool plugins and multiplexes them; the CLI MUST NOT start one `srun` step per skill.

#### Scenario: Two skills share one supervisor
- **WHEN** `--agent-skills=proc-monitor,node-diag` is set for a two-node job
- **THEN** each node runs a single supervisor that loads both tools

#### Scenario: Duplicate supervisor is rejected
- **WHEN** a second supervisor start is attempted for the same job id and host
- **THEN** the second start MUST fail or no-op without a second collector loop

### Requirement: Deterministic tool plugin contract
Each tool plugin SHALL implement start, event emission, stop, and artifact listing. `start` receives a job context (job id, host, output directory, match/interval as applicable). `events` SHALL report anomalies, not every sample. `stop` MUST be idempotent. `artifacts` SHALL return paths of files the tool wrote.

#### Scenario: Start then stop writes artifacts
- **WHEN** a plugin is started with a valid job context and later stopped
- **THEN** `artifacts` lists existing files under the job-scoped node directory and `stop` can be called twice without error

#### Scenario: Events are anomaly-oriented
- **WHEN** proc-monitor samples hundreds of JSONL lines with no threshold breach
- **THEN** `events` MAY be empty; sample points MUST NOT each become an event

### Requirement: Process monitor samples task PIDs
The `proc-monitor` tool SHALL sample matching task processes for CPU, RSS, and IO using process-level timeseries (host + pid, optional MPI rank), not whole-node averages. Matching and launcher exclusion MUST follow the mpi-monitor collect contract. The LLM MUST NOT scrape `/proc` as the primary collector.

#### Scenario: Rank process is sampled
- **WHEN** a matched rank binary is running on the node
- **THEN** JSONL samples include `ts`, `host`, `pid`, `cpu_pct`, `rss_mb`, `io_read_bps`, and `io_write_bps`

#### Scenario: Launchers are excluded
- **WHEN** `srun`, `mpirun`, `orted`, `sshd`, or the supervisor pid is present
- **THEN** those pids MUST NOT be sampled as application tasks

### Requirement: SLURM, MPI, and node diagnostic tools
The supervisor SHALL be able to load `slurm-tap` (job state and accounting via `scontrol`/`sstat`/`sacct` when available), `mpi-scan` (stderr and known MPI abort patterns), `node-diag` (local OOM, cgroup tasks, filesystem hang signals), and `plot` (optional PNG from JSONL). Missing optional backends MUST be reported as tool errors, not as a crash of the user step.

#### Scenario: slurm-tap records job state
- **WHEN** `SLURM_JOB_ID` is set and `scontrol` is available
- **THEN** slurm-tap artifacts include job id, nodelist, and state or a recorded tool error if the command fails

#### Scenario: mpi-scan detects abort text
- **WHEN** tee'd stderr contains `MPI_Abort` or a documented PMIx abort pattern
- **THEN** mpi-scan emits an event with a stable reason code and an evidence path

#### Scenario: plot is optional
- **WHEN** matplotlib is not installed
- **THEN** plot skips PNG files, warns, and leaves JSONL intact

### Requirement: Node-local store and fetch without shared filesystem
Each supervisor SHALL write under a job-scoped host directory. When no shared filesystem is available, the launch host MUST retrieve artifacts via `srun` fetch, SSH, or an inline payload. Compute nodes MUST NOT require a pre-installed copy of this package for collection.

#### Scenario: Local tmp then fetch
- **WHEN** the node has no shared filesystem with the launch host
- **THEN** artifacts appear under a host-local temp directory during the job and are fetched to the launch output directory after stop

#### Scenario: Inline payload on remote node
- **WHEN** a compute node has `python3` and `/proc` but not this package
- **THEN** collection still runs via an inline payload or equivalent, or a per-host collect error is recorded without hanging the CLI

### Requirement: proc-monitor samples until stop
The `proc-monitor` tool SHALL sample matching task processes for CPU, RSS, and
IO until the supervisor stops. Matching SHALL use `--match` (user binary
basename, overridable by `--agent-match`). Sampling MUST follow the
mpi-monitor collect contract (JSONL fields, launcher exclusion, stop file).
A one-shot empty start without a collector MUST NOT be the default when a
collect loop is available. Import failure of the collector MUST be recorded
as a collect error and MUST NOT change the user exit code.

#### Scenario: Collect loop runs until stop
- **WHEN** proc-monitor starts with an injected collect loop and later stops
- **THEN** the loop is invoked with match, interval, host, output directory,
  and a stop file, and stop writes that file so the loop can exit

#### Scenario: Supervisor argv includes match and interval
- **WHEN** wrap starts an overlap supervisor for a user binary `mpi_io_load`
- **THEN** supervisor argv includes `--match` (that basename or `--agent-match`)
  and `--interval`

#### Scenario: Missing mpi-monitor import is fail-soft
- **WHEN** the default collect loop cannot be imported
- **THEN** wrap still returns the user command exit code and records a
  collect error

### Requirement: Match comes from the user binary or an override
`--match` MUST be the basename of the user command after `--` unless
`--agent-match` is set. Launchers (`srun`, `mpirun`, `orted`, …) MUST NOT be
used as the match string.

#### Scenario: Agent-match overrides basename
- **WHEN** the user passes `--agent-match=mpi_io_load` with a different argv0
- **THEN** supervisor `--match` is `mpi_io_load`
