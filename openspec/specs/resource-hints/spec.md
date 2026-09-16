# resource-hints Specification

## Purpose

Defines wrap-time numbered Simplified Chinese `JobAssistNote` text from
`JobTelemetry` numeric summary heuristics, including healthy jobs, always
with a 建议 item and without embedding JSONL bodies.

## Requirements

### Requirement: Healthy wrap notes include resource suggestions
When job-assist wrap has no live summary and no pack `assist/job.json`, the
submit host SHALL write `assist/job.json` from `JobTelemetry` numeric
`summary` (and empty or present `anomalies`) without embedding JSONL bodies.
The human `summary` MUST be Simplified Chinese numbered items covering
conclusion, sampled host/pid/CPU/RSS/IO/ethernet, anomalies, and a
**建议** item. Healthy `reason_code=ok` jobs MUST still receive that 建议
item. `suspected_reason` MUST copy `reason_code`. `actions` MUST be `[]`.

#### Scenario: Successful MPI wrap with sampled PIDs
- **WHEN** wrap completes with `reason_code=ok`, `pid_count>=1`, and no
  live.json
- **THEN** `assist/job.json` exists, OpenCode is not spawned, and `summary`
  contains a numbered 建议 line derived from CPU/RSS/IO/ethernet peaks

#### Scenario: Exit 0 with zero PIDs still advises match
- **WHEN** wrap completes with user exit 0 and `pid_count=0`
- **THEN** the 建议 item mentions `--agent-match` or collector import / PYTHONPATH

#### Scenario: Ethernet disclaimer
- **WHEN** `summary` includes a non-null `eth_rx_bps_peak` or `eth_tx_bps_peak`
- **THEN** the 建议 item states host NIC rates are not MPI message bytes
