# job-telemetry Specification

## Purpose

Defines the job-scoped telemetry document, artifact layout, and how summaries reach the submitter or job-level agent without feeding raw high-frequency samples to an LLM.

## Requirements

### Requirement: JobTelemetry document exists at job end
After sidecars stop, the launch host SHALL write a `JobTelemetry` JSON document for the run. The document MUST include `summary`, `anomalies`, `evidence_paths`, and `reason_code`. When node-assist ran, it MUST include `node_assist`. When a retry policy applies, it MUST include `retry_allowed` and `attempt`.

#### Scenario: Successful tools-only job
- **WHEN** the user command exits 0 and collection completed
- **THEN** `JobTelemetry` exists with `reason_code` indicating success, a numeric summary, empty or absent blocking anomalies, and paths to meta/series files

#### Scenario: User failure preserved with telemetry
- **WHEN** the user command exits non-zero
- **THEN** `JobTelemetry` is still written, `reason_code` reflects the classified outcome, and the CLI exit code remains the user command's code

### Requirement: Summary is the LLM primary input
Any assist agent that interprets the job MUST use `summary` and `anomalies` as the primary input. Raw JSONL MUST be referenced only via `evidence_paths` and MUST NOT be required in the model prompt.

#### Scenario: Summary fields present
- **WHEN** at least one process series exists
- **THEN** `summary` includes peak and average CPU, peak RSS, IO totals or rates, host count, and sampled pid count as numbers or documented nulls

#### Scenario: LLM is not given every sample
- **WHEN** job-assist runs after a long series
- **THEN** the assist input document does not embed every JSONL line

### Requirement: Run directory layout
Each run SHALL use a directory containing at least `telemetry.json` (the `JobTelemetry` document), `meta.json`, `series/` for JSONL, and optional `charts/`, `events/`, and `assist/`. Paths MUST be relative to the configured output directory; implementations MUST NOT hardcode user homes.

#### Scenario: Layout after wrap
- **WHEN** a tools-only wrap completes with samples and no plots
- **THEN** the run directory contains `telemetry.json`, `meta.json`, and at least one file under `series/`, and `charts/` MAY be absent

#### Scenario: Node assist notes land under assist
- **WHEN** node-assist writes a `NodeAssistNote`
- **THEN** the note is stored under `assist/` and listed in `node_assist` and `evidence_paths`

### Requirement: Transport without shared filesystem
When compute nodes cannot write the launch output directory directly, the system MUST copy node artifacts to the launch run directory after stop. Fetch MUST be bounded by a timeout. Per-host fetch failure MUST be recorded in telemetry and MUST NOT hang the CLI indefinitely.

#### Scenario: Fetch after stop
- **WHEN** a remote node wrote JSONL under local temp
- **THEN** after stop those files appear under the launch run `series/` directory or `collect_errors` (or equivalent) names the host

#### Scenario: Fetch timeout is bounded
- **WHEN** a remote fetch exceeds the join timeout
- **THEN** the CLI proceeds, records a collect error for that host, and still writes `JobTelemetry`

### Requirement: Closed-loop consumers
The telemetry consumer SHALL be the submitting CLI report, an in-allocation job-assist agent, or a login-side analysis agent started by this CLI. The system MUST NOT require an external orchestration bus to produce `JobTelemetry`.

#### Scenario: CLI prints report from telemetry
- **WHEN** tools-only completes
- **THEN** the CLI writes `JobTelemetry` and a human-readable report derived from it without calling an external workflow runner

### Requirement: Human-readable report is compact
The submitting CLI human-readable report (`report.txt` and quiet stdout) SHALL
lead with run path, exit code, `reason_code`, host count, and pid count; then
the job-assist numbered summary when `assist/job.json` exists; then a compact
metrics line; then hosts grouped from `series/{host}_pid{pid}.jsonl` filenames;
then collect errors only when non-empty; then evidence as directory counts.
The report MUST NOT list every PNG path under `charts/`.

#### Scenario: Job-assist precedes evidence
- **WHEN** `assist/job.json` contains a summary
- **THEN** that summary appears before the evidence line

#### Scenario: Charts collapsed to a count
- **WHEN** `charts/` contains multiple PNG files
- **THEN** the report includes a `charts/` count and does not list each PNG path

#### Scenario: Empty collect_errors omitted
- **WHEN** telemetry has no collect errors
- **THEN** the report does not print an empty collect_errors object

### Requirement: Wrap-time telemetry is complete before assist
After sidecars stop and before any job-assist model call, the launch host SHALL
write `JobTelemetry` whose `summary` includes peak and average CPU, peak RSS,
IO totals or rates, host count, and sampled pid count as numbers or documented
nulls when series exist or are empty. `anomalies` MUST include tool events.
`reason_code` MUST come from classification, not from a model.

#### Scenario: Series populate numeric summary
- **WHEN** at least one process series exists at wrap end
- **THEN** `telemetry.json` `summary` includes `cpu_avg`, `cpu_peak`,
  `rss_peak_mb`, IO fields, `host_count`, and `pid_count`

#### Scenario: Tool events become anomalies before the model
- **WHEN** a tool emitted `mpi_abort` and job-assist is enabled
- **THEN** `anomalies` contains `mpi_abort` before the model is invoked

### Requirement: Live series and optional charts before assist
After sidecars stop and before any job-assist OpenCode spawn, the launch host
SHALL write `JobTelemetry` whose `summary` includes peak and average CPU, peak
RSS, IO totals or rates, host count, and sampled pid count as numbers or
documented nulls. When series files exist, optional PNG charts MUST be written
under `charts/` when a plotter is available; missing matplotlib MUST skip PNG
and keep JSONL. `evidence_paths` MUST list series and any written charts.
`reason_code` MUST come from classification, not from a model.

#### Scenario: Series populate numeric summary
- **WHEN** at least one process series exists at wrap end
- **THEN** `telemetry.json` `summary` includes `cpu_avg`, `cpu_peak`,
  `rss_peak_mb`, IO fields, `host_count`, and `pid_count`

#### Scenario: Charts listed when a plotter writes PNG
- **WHEN** series exist and a plotter returns PNG paths
- **THEN** those paths appear under `charts/` and in `evidence_paths`

#### Scenario: Missing matplotlib keeps JSONL
- **WHEN** series exist and matplotlib is unavailable
- **THEN** PNG files are skipped, JSONL remains, and wrap continues

### Requirement: Job-assist output is listed on telemetry
When job-assist writes a note, `JobTelemetry` MUST include `job_assist`
pointing at the note path, and `evidence_paths` MUST list that path.

#### Scenario: job_assist field present after assist
- **WHEN** job-assist successfully writes a `JobAssistNote`
- **THEN** `telemetry.json` contains `job_assist` and the note path appears in
  `evidence_paths`

### Requirement: Live plot is not required for JobTelemetry
Writing `JobTelemetry` MUST NOT require the live plot HTTP server or any
external message bus. Overlay serve failure MUST be recorded as a collect
error when wrap attempted to start the server, and MUST NOT overwrite
`reason_code`.

#### Scenario: JobTelemetry exists without live plot
- **WHEN** wrap completes with `--agent-no-live-plot`
- **THEN** `telemetry.json` is still written with `summary`, `anomalies`,
  and `reason_code` from classification

#### Scenario: Live plot bind error does not change reason_code
- **WHEN** the overlay server fails to bind and the user command exits 0
  with no tool anomalies
- **THEN** `reason_code` remains the classified success code and
  `collect_errors` names `live_plot`

### Requirement: Analysis artifacts appear in evidence
When `assist/analysis.json` is written for a run, `JobTelemetry`
`evidence_paths` MUST list that path (on a subsequent telemetry rewrite or
analy refresh). When a pack creates `assist/job.json`, that path MUST also
appear under `evidence_paths` and MAY be referenced by `job_assist`.

#### Scenario: analysis.json listed after pack
- **WHEN** wrap or analy writes `assist/analysis.json`
- **THEN** a telemetry refresh lists `assist/analysis.json` in
  `evidence_paths`

### Requirement: Stderr capture may grow while the job runs
`events/stderr.tail` MAY be updated during the user step via incremental
flush. Classification and anomaly roll-up MUST still treat the final
tail file as authoritative at wrap end.

#### Scenario: Wrap-end classification uses final tail
- **WHEN** stderr was flushed mid-run and again at exit with `MPI_Abort`
- **THEN** wrap-end `anomalies` include `mpi_abort` from the final
  `events/stderr.tail`
