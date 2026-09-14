## ADDED Requirements

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

## MODIFIED Requirements

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
