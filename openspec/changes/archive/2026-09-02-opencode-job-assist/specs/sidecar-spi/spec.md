## ADDED Requirements

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
