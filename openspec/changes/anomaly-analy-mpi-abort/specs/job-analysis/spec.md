## Purpose

Defines deterministic, bounded job analysis packs and the submit-host
`agent analy` entry point so operators get reproducible Chinese summaries
after faults without letting a model invent `reason_code` or mutate SLURM.

## ADDED Requirements

### Requirement: Analysis pack writes analysis.json
When wrap or `agent analy` runs an analysis pack for a non-ok job, the
system SHALL write `assist/analysis.json` with English keys describing the
pack name, `reason_code`, evidence excerpts, and deterministic findings.
The pack MUST NOT overwrite `JobTelemetry.reason_code`. Packs MUST be
selected from a fixed table keyed by tool `reason_code` (and documented
guards such as `pid_count=0` for launch failure), not by free-form model
choice.

#### Scenario: mpi_abort pack after abort telemetry
- **WHEN** `reason_code` is `mpi_abort` and analysis runs on a run directory
  with `events/stderr.tail` containing `MPI_Abort`
- **THEN** `assist/analysis.json` exists with pack `mpi_abort` and excerpts
  derived from stderr (and series summary when samples exist)

#### Scenario: reason_code unchanged
- **WHEN** analysis completes successfully
- **THEN** `telemetry.json` `reason_code` remains the tool/rollup value

### Requirement: job.json only when missing
A pack SHALL write `assist/job.json` only when that file does not already
exist. The note MUST use Simplified Chinese numbered-list `summary`, copy
`suspected_reason` from `reason_code`, set `actions` to `[]`, and MUST NOT
invoke `scancel` or `scontrol`.

#### Scenario: Pack fills empty assist note
- **WHEN** analysis runs and `assist/job.json` is absent
- **THEN** `assist/job.json` is written with empty `actions` and
  `suspected_reason` equal to telemetry `reason_code`

#### Scenario: Existing job.json preserved
- **WHEN** `assist/job.json` already exists (for example from live promote)
- **THEN** analysis still updates `assist/analysis.json` and does not
  replace the existing `job.json` summary

### Requirement: agent analy is offline and bounded
The CLI SHALL provide `agent analy --run-dir DIR` on the submit host. It
MUST NOT start compute-node sidecars and MUST NOT call `scancel` or
`scontrol`. Optional `--code PATH` MUST be read-only with documented
byte/file limits. Optional `--llm` MAY invoke OpenCode with an injected
runner in tests; without `--llm`, analysis MUST remain deterministic only.
Unit tests MUST NOT execute a real `opencode` binary.

#### Scenario: Deterministic analy without LLM
- **WHEN** the operator runs `agent analy --run-dir DIR` without `--llm`
- **THEN** `assist/analysis.json` is written and no OpenCode runner is
  invoked

#### Scenario: Code flag is required for source scan
- **WHEN** `--code` is omitted
- **THEN** analysis does not read user source trees outside the run
  directory evidence paths

#### Scenario: Code scan is read-only
- **WHEN** `--code=/path/to/src` is set
- **THEN** analysis may search that tree for `MPI_Abort` / binary basename
  references within size limits and MUST NOT compile or write under that
  tree

### Requirement: mpi_abort is the first implemented pack
The system SHALL implement the `mpi_abort` pack in this change. Expansion
packs for `slurm_oom` / `node_local`, `node_fail`, and `io_stall` MAY be
named in routing stubs but MUST NOT be required for this change's
acceptance.

#### Scenario: Unknown future codes fail soft
- **WHEN** `reason_code` has no implemented pack beyond documented stubs
- **THEN** analysis records a collect-style note or empty findings without
  hanging and without inventing a new primary `reason_code`
