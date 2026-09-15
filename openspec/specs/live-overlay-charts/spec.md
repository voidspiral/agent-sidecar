# live-overlay-charts Specification

## Purpose

Lets operators watch mpi-monitor CPU, RSS, and IO timeseries plus host
ethernet rx/tx in a browser on the submit host: one chart per metric, every
sampled process or NIC overlaid, with a legend, while JSONL files are still
growing.

## Requirements

### Requirement: Overlay snapshot groups processes by metric
The submit-host live plot consumer SHALL read `series/{host}_pid{pid}.jsonl`
and produce a snapshot in which each of `cpu_pct`, `rss_mb`, `io_read_bps`,
and `io_write_bps` contains one series per sampled process. Legend identity
MUST prefer MPI rank when present (`host rN`), otherwise `host pid PID`.
The snapshot MUST NOT require a message queue or database.

#### Scenario: Two processes overlay on CPU
- **WHEN** `series/` contains `cn1_pid1.jsonl` and `cn2_pid2.jsonl` with
  `cpu_pct` samples
- **THEN** the CPU overlay contains two series with distinct legend ids

#### Scenario: Growing JSONL appears in a later snapshot
- **WHEN** a new JSONL line is appended after a snapshot
- **THEN** a subsequent snapshot for that process includes the additional point

#### Scenario: Empty series is not an error
- **WHEN** `series/` is missing or has no JSONL files
- **THEN** the snapshot lists empty series for each metric and MUST NOT fail

### Requirement: Overlay snapshot groups ethernet by host and iface
The submit-host live plot consumer SHALL also read `series/{host}_net.jsonl`
and produce snapshot metrics `eth_rx_bps` and `eth_tx_bps` with one series
per host+iface. Legend identity MUST be `host iface` (for example
`cn1 eth0`). Net samples MUST NOT require a `pid` field. Process overlays
MUST ignore net JSONL so they are not filled with zero CPU/RSS/IO.

#### Scenario: Two hosts overlay on ethernet rx
- **WHEN** `series/` contains `cn1_net.jsonl` and `cn2_net.jsonl` with
  `eth_rx_bps` samples
- **THEN** the ethernet-rx overlay contains two series labeled `cn1 eth0`
  (or the iface present) and `cn2 …`

#### Scenario: Net JSONL does not pollute process charts
- **WHEN** `series/` contains both `{host}_pid{pid}.jsonl` and
  `{host}_net.jsonl`
- **THEN** `cpu_pct` series count equals the pid files and is not increased
  by the net file

#### Scenario: Growing net JSONL appears in a later snapshot
- **WHEN** a new net JSONL line is appended after a snapshot
- **THEN** a subsequent snapshot for that iface includes the additional point

### Requirement: Browser page overlays all traces of one metric
The live plot HTTP service SHALL serve a page that draws six charts (CPU,
RSS, IO read, IO write, ethernet rx, ethernet tx). Each process chart MUST
overlay every process series for that metric. Each ethernet chart MUST
overlay every host+iface series for that metric. The page MUST load without
an external CDN.

#### Scenario: Page and snapshot endpoints exist
- **WHEN** the service is bound to a run directory
- **THEN** `GET /` returns HTML with chart canvases including ethernet rx/tx
  and `GET /api/snapshot` returns JSON overlay data for process and ethernet
  metrics

#### Scenario: Axis titles explain elapsed time and units
- **WHEN** the operator opens `GET /`
- **THEN** each chart x-axis is labeled as elapsed time in seconds and the
  y-axis is labeled with that metric's unit

#### Scenario: Soft cap does not drop payload series
- **WHEN** more than 48 process series exist for a metric
- **THEN** the snapshot still includes all series and marks which are shown
  by default (highest CPU peak first)

#### Scenario: Ethernet soft cap uses rx peak
- **WHEN** more than 48 ethernet series exist
- **THEN** the snapshot still includes all ethernet series and marks which
  are shown by default (highest `eth_rx_bps` peak first)

### Requirement: agent serve tails a run directory
The CLI SHALL provide `agent serve --run-dir DIR` on the submit host, binding
`127.0.0.1:8765` by default, with optional `--host` and `--port`.

#### Scenario: Serve a finished run for replay
- **WHEN** the operator runs `agent serve --run-dir` on a completed run
- **THEN** the snapshot is built from existing JSONL without starting
  compute-node collectors
