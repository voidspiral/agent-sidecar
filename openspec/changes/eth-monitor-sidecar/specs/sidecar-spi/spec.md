## ADDED Requirements

### Requirement: eth-monitor samples host ethernet until stop
The supervisor SHALL be able to load `eth-monitor`, which samples host
ethernet rx/tx rates via the eth-monitor collect contract (JSONL fields
`ts`, `host`, `iface`, `eth_rx_bps`, `eth_tx_bps`; file
`series/{host}_net.jsonl`; stop file; no process match). Healthy NIC
timeseries MUST NOT become events. Missing eth-monitor import MUST be
recorded as a collect error and MUST NOT change the user exit code. The
LLM MUST NOT scrape `/proc/net` as the primary collector.

#### Scenario: Collect loop runs until stop
- **WHEN** eth-monitor starts with an injected collect loop and later stops
- **THEN** the loop is invoked with host, interval, output directory, and a
  stop file, and stop writes that file so the loop can exit

#### Scenario: Missing eth-monitor import is fail-soft
- **WHEN** the default collect loop cannot be imported
- **THEN** wrap still returns the user command exit code and records a
  collect error under `events/eth_monitor_import.err`

#### Scenario: Healthy ethernet series is not an event
- **WHEN** eth-monitor writes hundreds of JSONL lines with no other tool
  anomaly
- **THEN** `eth-monitor` `events` MAY be empty
