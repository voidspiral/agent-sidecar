## ADDED Requirements

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
