## ADDED Requirements

### Requirement: Wrap job-assist note exists without a model
After `JobTelemetry` is written, job-assist wrap SHALL persist
`assist/job.json` and list it under `job_assist` / `evidence_paths` even when
no OpenCode process ran. A healthy job with sampled series MUST include
resource suggestions in the note. A pack note already present MUST be kept.

#### Scenario: Healthy job lists job_assist from hints
- **WHEN** wrap completes with `reason_code=ok` and job-assist enabled
- **THEN** `telemetry.json` contains `job_assist` pointing at `assist/job.json`

#### Scenario: Pack note is not replaced on default wrap
- **WHEN** wrap wrote `assist/job.json` from a deterministic pack and
  `AGENT_OPENCODE_FINAL_TIMEOUT` is unset
- **THEN** that file still has the pack summary after wrap returns
