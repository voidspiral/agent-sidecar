## Purpose

Defines the job-scoped telemetry document, artifact layout, and how summaries reach the submitter or job-level agent without feeding raw high-frequency samples to an LLM.

## ADDED Requirements

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
