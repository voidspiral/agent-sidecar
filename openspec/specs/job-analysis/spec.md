# job-analysis Specification

## Purpose

Defines deterministic, bounded job analysis packs and the submit-host
`agent analy` entry point so operators get reproducible Chinese summaries
after faults without letting a model invent `reason_code` or mutate SLURM.

## Requirements

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

### Requirement: Quiet report suggests sidecar-analy.sh
When wrap writes the quiet run report and `reason_code` is not `ok`, the
report MUST include a next-step line that invokes
`sidecar-analy.sh --log <run_dir> --code /path/to/src` (or equivalent
placeholder). The report MUST still print the run directory path.

#### Scenario: Non-ok report names analy script
- **WHEN** quiet wrap finishes a job with `reason_code=mpi_abort`
- **THEN** the printed report contains `sidecar-analy.sh` and `--log`
  pointing at that run directory

### Requirement: Phase-1 analysis forbids source line numbers
When analysis runs without `--code`, `assist/analysis.json` MUST set
`code_hits` to an empty list and `needs_source` to true, and MUST include
an `ask_code_cmd` string that invokes `sidecar-analy.sh --log` with a
`--code` placeholder. The Chinese `assist/job.json` summary (when written)
MUST ask the operator for a source tree and MUST NOT cite `file:line`
paths for user application source.

#### Scenario: No code flag means no line citations
- **WHEN** `agent analy --log DIR` or `agent analy --run-dir DIR` runs
  without `--code` for `mpi_abort`
- **THEN** `analysis.json` has empty `code_hits`, `needs_source` is true,
  and `job.json` summary contains a `--code` ask without a `.c:` line cite

### Requirement: Phase-2 authorized source scan may overwrite job.json
When `--code PATH` is set, analysis MAY scan that tree read-only, populate
`code_hits`, set `needs_source` to false, update `assist/analysis.json`,
and MAY overwrite `assist/job.json` with a summary that cites authorized
path hits. Prefer hits whose paths relate to the job binary basename when
known. Without `--code` and without LLM (`--no-llm`, or wrap's
deterministic pack call), an existing `job.json` MUST NOT be overwritten.

#### Scenario: Code flag allows job.json refresh
- **WHEN** phase-1 already wrote `assist/job.json` asking for source and
  the operator re-runs `agent analy --log DIR --code PATH` or
  `agent analy --run-dir DIR --code PATH`
- **THEN** `analysis.json` is updated with `code_hits` and `job.json`
  summary is replaced with a phase-2 note that may cite path:lineno under
  the authorized tree

#### Scenario: Plain re-analy preserves job.json
- **WHEN** `assist/job.json` exists and analy runs again without `--code`
  and with `--no-llm`
- **THEN** `job.json` summary is unchanged

### Requirement: job.json only when missing for phase-1
A phase-1 pack (no `--code`, no LLM) SHALL write `assist/job.json` only
when that file does not already exist. The note MUST use Simplified
Chinese numbered-list `summary`, copy `suspected_reason` from
`reason_code`, set `actions` to `[]`, and MUST NOT invoke `scancel` or
`scontrol`.

#### Scenario: Pack fills empty assist note
- **WHEN** analysis runs without `--code` and without LLM and
  `assist/job.json` is absent
- **THEN** `assist/job.json` is written with empty `actions` and
  `suspected_reason` equal to telemetry `reason_code`

#### Scenario: Existing job.json preserved without code
- **WHEN** `assist/job.json` already exists (for example from live promote)
  and analysis runs without `--code` and without LLM
- **THEN** analysis still updates `assist/analysis.json` and does not
  replace the existing `job.json` summary

### Requirement: agent analy is offline and bounded
The CLI SHALL provide `agent analy --log DIR` (alias `--run-dir DIR`) on
the submit host. It MUST NOT start compute-node sidecars and MUST NOT call
`scancel` or `scontrol`. Optional `--code PATH` MUST be read-only with
documented byte/file limits. Analysis MUST invoke OpenCode by default
(including when `--llm` is passed). `--no-llm` MUST keep analysis
deterministic only. Unit tests MUST NOT execute a real `opencode` binary.
Missing OpenCode MUST remain fail-soft: packs still write
`assist/analysis.json`.

#### Scenario: Deterministic analy without LLM
- **WHEN** the operator runs `agent analy --log DIR --no-llm` (or
  `--run-dir DIR --no-llm`)
- **THEN** `assist/analysis.json` is written and no OpenCode runner is
  invoked

#### Scenario: Default analy invokes OpenCode
- **WHEN** the operator runs `agent analy --log DIR` without `--no-llm`
- **THEN** the OpenCode runner path is invoked after the deterministic
  pack (injected in unit tests)

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
When `agent analy` runs with LLM enabled (the default, or explicit
`--llm`), the OpenCode prompt MUST include the current
`assist/analysis.json` contents (or an equivalent structured embed)
together with the telemetry contract so a new `opencode run` can continue
from disk without relying on a prior chat session. The prompt MUST
instruct: trust pack fields; if `needs_source` or empty `code_hits`, ask
for `--code` and do not invent line numbers; if hits exist, cite only
authorized paths. `--no-llm` MUST skip this prompt.

#### Scenario: Prompt carries analysis pack fields
- **WHEN** LLM analy runs and `assist/analysis.json` contains
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
