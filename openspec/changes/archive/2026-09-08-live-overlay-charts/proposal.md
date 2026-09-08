## Why

Operators can already collect per-process CPU/RSS/IO while a job runs
(`series/{host}_pid{pid}.jsonl`), but the only charts are wrap-time matplotlib
PNGs, one file per pid × metric. They need a browser on the submit host (`mn`)
to watch **all ranks of one metric overlayed on a single chart** with a legend,
while the job is still running.

## What Changes

- Submit-host `agent serve --run-dir DIR` tails growing JSONL and serves a
  self-contained overlay page (four charts: cpu, rss, io read, io write).
- `agent srun` starts that server beside the live OpenCode watcher (default on),
  prints the URL even in quiet mode, and stops it when the user step ends.
  Replay a finished run with `agent serve` after wrap.
- Bind/port failures are fail-soft (`collect_errors.live_plot`); they MUST NOT
  change the user exit code or `reason_code`.
- Wrap-time per-pid PNG under `charts/` stays. Compute-node `proc-monitor` and
  mpi-monitor `collect_loop` stay. No Redis/SQLite/NATS.

## Non-goals

- No ClusterHelm control-plane integration: do not reuse, adapt, or consume
  Master/Slave, `workflow_runner`, `partition_report`, `run-slave.sh`,
  submit/wait, or gateway preflight/exclusion policy.
- No message queue or database on compute nodes or as a JobTelemetry dependency.
- No Grafana / Prometheus.
- No replacing wrap PNG with one synthetic overlay file.
- No heatmap / drill-down UI (soft cap + legend toggle only).
- No OpenCode generating or interpreting overlay charts; models stay text-only.
- No scraping `/proc` from the submit host or from OpenCode.
- No automatic `webbrowser.open` (login nodes often have no DISPLAY).

## Capabilities

### New Capabilities

- `live-overlay-charts`: JSONL tail on the submit host, overlay snapshot JSON
  per metric, stdlib HTTP UI with legend, `agent serve`, wrap-time start/stop.

### Modified Capabilities

- `agent-launch`: wrap MAY start a submit-host live-plot HTTP server with the
  user step and MUST stop it when the user step returns; flag opt-out.
- `job-telemetry`: live plot MUST NOT be required to write `JobTelemetry`;
  bind failure is a collect error only.

## Impact

- **Code:** new `live_plot` / `live_plot_http`, static HTML + vendored Chart.js,
  `agent serve`, wrap lifecycle, `--agent-live-plot` / `--agent-no-live-plot`.
- **Ops:** operator opens `http://127.0.0.1:8765` on `mn`, or SSH `-L` from a
  laptop. No new pip dependencies.
- **Tests:** unittest with fixture JSONL and `http.client`; no real browser, no
  live `/proc`, no Redis.
- **Neighbors:** mpi-monitor collect contract unchanged.
