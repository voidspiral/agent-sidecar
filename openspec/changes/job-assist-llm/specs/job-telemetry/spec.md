## ADDED Requirements

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

### Requirement: Job-assist output is listed on telemetry
When job-assist writes a note, `JobTelemetry` MUST include `job_assist` pointing
at the note path, and `evidence_paths` MUST list that path.

#### Scenario: job_assist field present after assist
- **WHEN** job-assist successfully writes a `JobAssistNote`
- **THEN** `telemetry.json` contains `job_assist` and the note path appears in
  `evidence_paths`
