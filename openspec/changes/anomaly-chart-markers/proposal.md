## Why

Live overlay and wrap-time PNG charts already show CPU/RSS/IO/ethernet
timeseries, but classified faults (`mpi_abort`, `mpi_segfault`, `slurm_oom`,
`node_local`) never appear on the time axis. Operators cannot see *when* a
known tool event landed relative to the curves. Abort-era work listed chart
boxes as a non-goal; that gap is now the next slice.

## What Changes

- Record a first-seen Unix-epoch `ts` for the four existing point events.
- Persist append-only per-host marker JSONL under `events/` so live ingest and
  wrap plotters do not parse stderr/dmesg themselves.
- Merge optional `ts` onto `telemetry.anomalies` without changing
  `reason_code` rollup order.
- Draw a vertical line plus a host/`reason_code` label box on live Chart.js
  (all six metric charts) and wrap matplotlib PNGs (process and eth/TCP).
- Healthy CPU/ethernet jitter still MUST NOT become markers or live OpenCode
  triggers. Models stay text-only and MUST NOT look at PNG pixels.

## Non-goals

- No ClusterHelm control-plane integration: do not reuse, adapt, or consume
  Master/Slave, `workflow_runner`, `partition_report`, `run-slave.sh`,
  submit/wait, or gateway preflight/exclusion policy.
- No model-from-image anomaly detection.
- No live OpenCode from healthy series (CPU/RSS/IO/ethernet/TCP).
- No P2 duration detectors (`cpu_idle`, `rank_imbalance`, `io_stall`) or
  shaded time ranges (`start_ts`/`end_ts`).
- No changing primary `reason_code` selection.
- No `scancel` / `scontrol` mutation, no new pip/CDN Chart.js plugins.
- No inventing a more precise fault instant than first detection time.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `sidecar-spi`: `Event` MAY carry `ts`; plugins and wrap persist first-seen
  chart markers for the four point codes without emitting sample-level events.
- `job-telemetry`: `anomalies` MAY include optional `ts` from marker files;
  missing markers on old runs keep the previous dict shape; rollup unchanged.
- `live-overlay-charts`: snapshot includes `markers` in elapsed seconds; the
  browser and wrap PNGs annotate those points; empty markers MUST NOT change
  existing overlay or PNG behavior.

## Impact

- Code: new marker helper; `spi.Event`; wrap stderr flush; `slurm-tap` /
  `node-diag` / `mpi-scan`; `telemetry.anomalies_from_artifacts`; live ingest
  and HTML; matplotlib plotter plus eth-monitor writer injection.
- Artifacts: `events/{host}_markers.jsonl` and `events/submit_markers.jsonl`.
- Tests: unittest only; no Selenium; no live `/proc`.
- Neighbors: do not patch the eth-monitor repo; pass a marker-aware writer.
