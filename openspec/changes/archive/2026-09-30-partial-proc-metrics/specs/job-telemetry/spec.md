# job-telemetry Specification

## ADDED Requirements

### Requirement: Null process metrics stay null in the summary
`summarize_series` SHALL keep `cpu_peak`, `rss_peak_mb`, `io_read_bps_sum`, and `io_write_bps_sum` as JSON `null` when every sample for that metric is `null`. A numeric `0` SHALL remain `0` and SHALL NOT set `summary.unavailable`. When any sample lists `unavailable`, the summary SHALL include that list.

#### Scenario: RSS or CPU without io
- **WHEN** a pid JSONL line has a non-zero `cpu_pct` or `rss_mb`, null IO fields, and `unavailable` containing `io`
- **THEN** `cpu_peak` or `rss_peak_mb` is numeric, both IO sums are `null`, and `summary.unavailable` contains `io`

#### Scenario: Zero IO is not a kernel gap
- **WHEN** IO fields are numeric `0` and `unavailable` is absent
- **THEN** the IO sums are `0` and `summary.unavailable` is empty
