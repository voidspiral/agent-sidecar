## ADDED Requirements

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
