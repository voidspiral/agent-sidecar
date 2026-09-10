## ADDED Requirements

### Requirement: mpi_segfault pack after segfault telemetry
When `reason_code` is `mpi_segfault` and analysis runs, the system SHALL
write `assist/analysis.json` with pack `mpi_segfault`, stderr-derived
`fault_rank` when parseable, optional `signal` (for example 11), series
brief when samples exist, empty `code_hits` and `needs_source=true` without
`--code`, and an `ask_code_cmd`. Phase-1 Chinese `job.json` (when written)
MUST NOT cite application `file:line` paths. Phase-2 `--code` MAY populate
`code_hits` (preferring the job binary basename) and overwrite `job.json`.

#### Scenario: Phase-1 mpi_segfault pack
- **WHEN** `reason_code` is `mpi_segfault` and analysis runs without `--code`
  on a run directory whose `events/stderr.tail` contains
  `rank 0 segfault`
- **THEN** `assist/analysis.json` has pack `mpi_segfault`, empty
  `code_hits`, `needs_source` true, and `job.json` summary (if newly
  written) asks for `--code` without a `.c:` line cite

#### Scenario: Phase-2 authorized scan for segfault fixture
- **WHEN** the operator re-runs `agent analy --run-dir DIR --code PATH`
  containing `mpi_fault_segfault.c`
- **THEN** `analysis.json` may include `code_hits` and `job.json` may cite
  authorized path:lineno under that tree

#### Scenario: reason_code unchanged by pack
- **WHEN** the `mpi_segfault` pack completes
- **THEN** `telemetry.json` `reason_code` remains `mpi_segfault`
