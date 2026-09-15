## ADDED Requirements

### Requirement: Anomalies MAY include first-seen timestamps
When chart-marker JSONL exists for a run, `JobTelemetry.anomalies` entries
for `mpi_abort`, `mpi_segfault`, `slurm_oom`, and `node_local` SHALL include
optional `ts` copied from the matching first-seen marker. Runs without marker
files MUST keep the previous anomaly dict shape (no required `ts`). Marker
presence MUST NOT change `reason_code` rollup order.

#### Scenario: Marker ts merges onto abort anomaly
- **WHEN** `events/stderr.tail` classifies `mpi_abort` and a submit marker
  exists for that code and evidence path
- **THEN** the telemetry anomaly for `mpi_abort` includes the marker `ts`
  and `reason_code` remains `mpi_abort`

#### Scenario: Old run without markers omits ts
- **WHEN** `events/` has classified artifacts but no `*_markers.jsonl`
- **THEN** `anomalies_from_artifacts` still returns reason codes and
  evidence paths and MUST NOT require a `ts` field

#### Scenario: Rollup order unchanged by ts
- **WHEN** both `mpi_abort` and `slurm_oom` artifacts exist
- **THEN** `reason_code` is still the first classified anomaly in the
  existing artifact-scan order, not the numerically earliest `ts`
