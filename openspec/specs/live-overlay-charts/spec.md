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

### Requirement: Overlay snapshot includes elapsed-time markers
The submit-host live plot consumer SHALL read `events/*_markers.jsonl` and
include a `markers` array in the snapshot. Each marker MUST expose
`reason_code`, `host`, and `x` as seconds relative to snapshot `t0` (first
series sample when present). Missing marker files MUST yield `markers: []`
and MUST NOT fail the snapshot. Growing marker files MUST appear in a later
poll. Markers outside the four point codes (`mpi_abort`, `mpi_segfault`,
`slurm_oom`, `node_local`) MUST be ignored.

#### Scenario: Abort marker is relative to series t0
- **WHEN** series samples start at ts 10.0 and a `mpi_abort` marker has ts 12.5
- **THEN** the snapshot contains a marker with `reason_code=mpi_abort` and
  `x=2.5`

#### Scenario: No marker files means empty markers
- **WHEN** `series/` has JSONL and `events/` has no `*_markers.jsonl`
- **THEN** `markers` is an empty list and metric series are unchanged

#### Scenario: Marker append appears in a later snapshot
- **WHEN** a new marker JSONL line is appended after a snapshot
- **THEN** a subsequent snapshot includes the additional marker

#### Scenario: Snapshot without series still succeeds
- **WHEN** `series/` is empty and a marker file exists
- **THEN** the snapshot MUST NOT fail and MUST include `markers`

### Requirement: Browser overlays marker lines on every metric chart
The live plot page SHALL draw a vertical line and a label box
(`host` plus `reason_code`) for each snapshot marker on all six metric
charts. The page MUST NOT load an annotation plugin from a CDN. Healthy
series jitter without markers MUST leave charts without those overlays.

#### Scenario: HTML includes marker drawing
- **WHEN** the operator opens `GET /`
- **THEN** the page source includes marker-line drawing for the six canvases
  and does not reference an external annotation CDN

#### Scenario: Snapshot schema exposes markers
- **WHEN** `GET /api/snapshot` runs for a fixture with one `node_local` marker
- **THEN** the JSON body contains `markers` with that `reason_code` and `host`

### Requirement: Wrap PNG annotates the same markers
When matplotlib is available, wrap-time process PNGs and eth/TCP PNGs SHALL
draw a vertical line and a host/`reason_code` label at each marker `ts` that
falls inside that chart's sample time range. Markers outside the range MUST
be omitted. Missing matplotlib or missing markers MUST leave JSONL intact
and MUST NOT fail wrap.

#### Scenario: In-range marker draws on process PNG
- **WHEN** a process JSONL spans ts 1..10 and a `mpi_abort` marker has ts 5
- **THEN** the process plot path draws a vertical marker at ts 5

#### Scenario: Out-of-range marker is skipped
- **WHEN** a chart's samples span ts 1..10 and a marker has ts 50
- **THEN** that chart MUST NOT draw a vertical line for the marker

#### Scenario: No markers keeps JSONL and still plots
- **WHEN** wrap plots a run with series and no marker files
- **THEN** PNG generation still follows the existing optional-plot contract
  and JSONL remains
