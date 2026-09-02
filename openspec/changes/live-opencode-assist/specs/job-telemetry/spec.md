## MODIFIED Requirements

### Requirement: Wrap-time telemetry is complete before assist
After sidecars stop, the launch host SHALL write `JobTelemetry` whose `summary`
includes peak and average CPU, peak RSS, IO totals or rates, host count, and
sampled pid count as numbers or documented nulls when series exist or are
empty. `anomalies` MUST include tool events. `reason_code` MUST come from
classification, not from a model. The live watcher MAY run on partial
summaries before this document exists. The final OpenCode note MUST run only
after this wrap-time document is written.

#### Scenario: Series populate numeric summary
- **WHEN** at least one process series exists at wrap end
- **THEN** `telemetry.json` `summary` includes `cpu_avg`, `cpu_peak`,
  `rss_peak_mb`, IO fields, `host_count`, and `pid_count`

#### Scenario: Tool events become anomalies before the model
- **WHEN** a tool emitted `mpi_abort` and job-assist is enabled
- **THEN** `anomalies` contains `mpi_abort` before the final OpenCode note is
  invoked

### Requirement: Live series and optional charts before assist
After sidecars stop and before the final job-assist OpenCode note, the launch
host SHALL write `JobTelemetry` whose `summary` includes peak and average CPU,
peak RSS, IO totals or rates, host count, and sampled pid count as numbers or
documented nulls. When series files exist, optional PNG charts MUST be written
under `charts/` when a plotter is available; missing matplotlib MUST skip PNG
and keep JSONL. `evidence_paths` MUST list series and any written charts.
`reason_code` MUST come from classification, not from a model. Live watcher
ticks MAY occur before charts exist.

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

## ADDED Requirements

### Requirement: Live assist notes may appear before telemetry.json
During the user step, job-assist MAY write incremental files under `assist/`
(for example a live log or snapshot note). Those files MUST NOT replace
`reason_code`. After wrap, `telemetry.json` remains the authoritative
`JobTelemetry` document.

#### Scenario: Live note does not replace reason_code
- **WHEN** the live watcher writes under `assist/` before wrap-time telemetry
- **THEN** the later `telemetry.json` `reason_code` still comes from tools and
  is not overwritten by the live note
