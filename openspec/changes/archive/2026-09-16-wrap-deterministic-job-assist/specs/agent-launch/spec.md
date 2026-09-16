## ADDED Requirements

### Requirement: Wrap writes assist notes for ok jobs
After `JobTelemetry` is written, when `--agent-profile=job-assist` and
`reason_code` is `ok` with empty anomalies, wrap SHALL still write
`assist/job.json` with numbered Simplified Chinese suggestions from the
numeric summary. Missing OpenCode MUST NOT prevent that note.

#### Scenario: Healthy wrap still gets job.json
- **WHEN** the user step exits 0 with no tool anomalies and job-assist is on
- **THEN** wrap writes `assist/job.json` including a 建议 item without
  spawning OpenCode
