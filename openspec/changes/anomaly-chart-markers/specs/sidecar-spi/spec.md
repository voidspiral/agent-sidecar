## ADDED Requirements

### Requirement: Plugin events MAY carry a detection timestamp
Each tool `Event` MAY include `ts` as Unix epoch seconds (float), recorded at
first detection. Sample points MUST still not each become an event. Healthy
CPU, RSS, IO, ethernet, or TCP jitter MUST NOT emit chart-marker events.

#### Scenario: Anomaly event may include ts
- **WHEN** a plugin emits `mpi_abort`, `mpi_segfault`, `slurm_oom`, or
  `node_local`
- **THEN** the in-memory event MAY include a numeric `ts` and MUST still
  include `reason_code`

#### Scenario: Healthy series still produce no events
- **WHEN** proc-monitor or eth-monitor sample hundreds of JSONL lines with
  no classified fault
- **THEN** chart-marker artifacts for those tools MUST NOT be written

### Requirement: First-seen chart markers are per host
The system SHALL persist first-seen chart markers for `mpi_abort`,
`mpi_segfault`, `slurm_oom`, and `node_local` under the run `events/`
directory as append-only JSONL, one file per writer host
(`events/{host}_markers.jsonl`, submit-host `events/submit_markers.jsonl`).
Each line MUST include `ts`, `reason_code`, `evidence_path`, and `host`.
A later detection with the same `(reason_code, evidence_path, host)` MUST
keep the first `ts`. Compute nodes MUST NOT share a single JSONL writer.

#### Scenario: First MPI abort records one marker
- **WHEN** captured stderr first contains `MPI_Abort` during the user step
- **THEN** `events/submit_markers.jsonl` contains one `mpi_abort` line with
  a numeric `ts` and evidence path `events/stderr.tail`

#### Scenario: Duplicate detection keeps first ts
- **WHEN** the same host records `node_local` for the same evidence path twice
- **THEN** the marker file still has one matching line and `ts` is unchanged

#### Scenario: Two hosts write separate marker files
- **WHEN** `cn1` and `cn3` each emit `node_local`
- **THEN** markers land in `events/cn1_markers.jsonl` and
  `events/cn3_markers.jsonl` rather than one shared file
