## ADDED Requirements

### Requirement: Summary includes ethernet peaks without inflating pid count
`summarize_series` SHALL add `eth_rx_bps_peak` and `eth_tx_bps_peak` from
`series/{host}_net.jsonl` (null when absent). `pid_count` MUST count only
`*_pid*.jsonl` files (or samples that carry `pid`). Net JSONL MUST NOT
increment `pid_count`.

#### Scenario: Net file does not count as a pid
- **WHEN** `series/` contains one `{host}_pid{pid}.jsonl` and one
  `{host}_net.jsonl`
- **THEN** `pid_count` is 1 and `eth_rx_bps_peak` is the max `eth_rx_bps`
  in the net file

#### Scenario: Ethernet peaks null when no net series
- **WHEN** only process JSONL exists
- **THEN** `eth_rx_bps_peak` and `eth_tx_bps_peak` are null
