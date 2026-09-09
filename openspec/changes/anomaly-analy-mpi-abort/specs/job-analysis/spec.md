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

### Requirement: Phase-1 analysis forbids source line numbers
When analysis runs without `--code`, `assist/analysis.json` MUST set
`code_hits` to an empty list and `needs_source` to true, and MUST include
an `ask_code_cmd` string that invokes `agent analy --run-dir` with a
`--code` placeholder. The Chinese `assist/job.json` summary (when written)
MUST ask the operator for a source tree and MUST NOT cite `file:line`
paths for user application source.

#### Scenario: No code flag means no line citations
- **WHEN** `agent analy --run-dir DIR` runs without `--code` for `mpi_abort`
- **THEN** `analysis.json` has empty `code_hits`, `needs_source` is true,
  and `job.json` summary contains a `--code` ask without a `.c:` line cite

### Requirement: Phase-2 authorized source scan may overwrite job.json
When `--code PATH` is set, analysis MAY scan that tree read-only, populate
`code_hits`, set `needs_source` to false, update `assist/analysis.json`,
and MAY overwrite `assist/job.json` with a summary that cites authorized
path hits. Prefer hits whose paths relate to the job binary basename when
known. Without `--code` and without `--llm`, an existing `job.json` MUST
NOT be overwritten.

#### Scenario: Code flag allows job.json refresh
- **WHEN** phase-1 already wrote `assist/job.json` asking for source and
  the operator re-runs `agent analy --run-dir DIR --code PATH`
- **THEN** `analysis.json` is updated with `code_hits` and `job.json`
  summary is replaced with a phase-2 note that may cite path:lineno under
  the authorized tree

#### Scenario: Plain re-analy preserves job.json
- **WHEN** `assist/job.json` exists and analy runs again without `--code`
  and without `--llm`
- **THEN** `job.json` summary is unchanged

### Requirement: job.json only when missing for phase-1
A phase-1 pack (no `--code`, no `--llm`) SHALL write `assist/job.json`
only when that file does not already exist. The note MUST use Simplified
Chinese numbered-list `summary`, copy `suspected_reason` from
`reason_code`, set `actions` to `[]`, and MUST NOT invoke `scancel` or
`scontrol`.

#### Scenario: Pack fills empty assist note
- **WHEN** analysis runs without `--code`/`--llm` and `assist/job.json`
  is absent
- **THEN** `assist/job.json` is written with empty `actions` and
  `suspected_reason` equal to telemetry `reason_code`

#### Scenario: Existing job.json preserved without code
- **WHEN** `assist/job.json` already exists (for example from live promote)
  and analysis runs without `--code` and without `--llm`
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

### Requirement: LLM analy prompt rehydrates analysis.json
When `agent analy` runs with `--llm`, the OpenCode prompt MUST include the
current `assist/analysis.json` contents (or an equivalent structured
embed) together with the telemetry contract so a new `opencode run` can
continue from disk without relying on a prior chat session. The prompt
MUST instruct: trust pack fields; if `needs_source` or empty `code_hits`,
ask for `--code` and do not invent line numbers; if hits exist, cite only
authorized paths.

#### Scenario: Prompt carries analysis pack fields
- **WHEN** `--llm` is set and `assist/analysis.json` contains
  `abort_rank` / `needs_source`
- **THEN** the OpenCode prompt text includes those analysis fields

### Requirement: mpi_abort is the first implemented pack
The system SHALL implement the `mpi_abort` pack in this change. Expansion
packs for `slurm_oom` / `node_local`, `node_fail`, and `io_stall` MAY be
named in routing stubs but MUST NOT be required for this change's
acceptance.

#### Scenario: Unknown future codes fail soft
- **WHEN** `reason_code` has no implemented pack beyond documented stubs
- **THEN** analysis records a collect-style note or empty findings without
  hanging and without inventing a new primary `reason_code`
