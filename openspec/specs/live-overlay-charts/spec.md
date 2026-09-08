# live-overlay-charts Specification

## Purpose

Lets operators watch mpi-monitor CPU, RSS, and IO timeseries in a browser on
the submit host: one chart per metric, every sampled process overlaid, with a
legend, while JSONL files are still growing.

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

### Requirement: Browser page overlays all traces of one metric
The live plot HTTP service SHALL serve a page that draws four charts (CPU,
RSS, IO read, IO write). Each chart MUST overlay every process series for
that metric. The page MUST load without an external CDN.

#### Scenario: Page and snapshot endpoints exist
- **WHEN** the service is bound to a run directory
- **THEN** `GET /` returns HTML with chart canvases and `GET /api/snapshot`
  returns JSON overlay data

#### Scenario: Axis titles explain elapsed time and units
- **WHEN** the operator opens `GET /`
- **THEN** each chart x-axis is labeled as elapsed time in seconds and the
  y-axis is labeled with that metric's unit

#### Scenario: Soft cap does not drop payload series
- **WHEN** more than 48 process series exist for a metric
- **THEN** the snapshot still includes all series and marks which are shown
  by default (highest CPU peak first)

### Requirement: agent serve tails a run directory
The CLI SHALL provide `agent serve --run-dir DIR` on the submit host, binding
`127.0.0.1:8765` by default, with optional `--host` and `--port`.

#### Scenario: Serve a finished run for replay
- **WHEN** the operator runs `agent serve --run-dir` on a completed run
- **THEN** the snapshot is built from existing JSONL without starting
  compute-node collectors
