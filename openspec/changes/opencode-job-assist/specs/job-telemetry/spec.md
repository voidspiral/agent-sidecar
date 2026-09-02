## ADDED Requirements

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
