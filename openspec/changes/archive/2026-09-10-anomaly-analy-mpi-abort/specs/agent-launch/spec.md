## ADDED Requirements

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
