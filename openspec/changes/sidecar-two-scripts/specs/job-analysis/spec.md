## ADDED Requirements

### Requirement: Quiet report suggests sidecar-analy.sh
When wrap writes the quiet run report and `reason_code` is not `ok`, the
report MUST include a next-step line that invokes
`sidecar-analy.sh --log <run_dir> --code /path/to/src` (or equivalent
placeholder). The report MUST still print the run directory path.

#### Scenario: Non-ok report names analy script
- **WHEN** quiet wrap finishes a job with `reason_code=mpi_abort`
- **THEN** the printed report contains `sidecar-analy.sh` and `--log`
  pointing at that run directory

## MODIFIED Requirements

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
