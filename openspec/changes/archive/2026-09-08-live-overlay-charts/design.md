## Context

See `proposal.md` for motivation. Compute nodes already append
`series/{host}_pid{pid}.jsonl` via mpi-monitor `collect_loop`. Wrap writes
optional per-pid matplotlib PNGs after the user step. Live OpenCode on the
submit host already tails artifact snapshots (not `/proc`). There is no
browser UI. JobTelemetry MUST NOT depend on an external bus.

Constraints: Python 3.10+; stdlib first; no new pip dependencies; TDD with
`unittest` (failing tests first); unit tests MUST NOT open a real browser,
scrape live `/proc`, or require Redis. No hardcoded user homes. Sidecars
follow the job. Login nodes may be air-gapped (no CDN).

## Goals / Non-Goals

**Goals:**

- Tail JSONL on the submit host and overlay all processes per metric.
- Serve a self-contained page plus `/api/snapshot` with stdlib HTTP.
- Start/stop the server with wrap; keep `agent serve` for replay.
- Fail-soft on bind errors without changing user exit or `reason_code`.

**Non-Goals:**

- Message queues, databases, Grafana, ClusterHelm, replacing wrap PNGs,
  heatmap drill-down, OpenCode drawing charts, submit-host `/proc` scrape.

## Decisions

### 1. Implementation method: TDD

Write failing `unittest` cases first: fixture JSONL overlay payload, append
increases point count, empty series, `http.client` against an ephemeral port,
injectable live-plot server on wrap (start before `run_user`, stop after),
bind failure keeps user exit. Then implement until tests pass.

**Alternatives:** Selenium against Chart.js (rejected: flaky, not stdlib).
Real `srun` in unittest (rejected: needs the cluster).

### 2. JSONL is the log; HTTP is a consumer

mn tails byte offsets in `series/*.jsonl`. Incomplete last lines stay
unconsumed. Time axis is `ts` minus the first sample. Keep at most 900 points
per series (stride older samples). Soft cap 48: payload still lists every
series; `visible` is true for the 48 with highest `cpu_pct` peak.

**Alternatives:** Redis/NATS (rejected: extra failure domain; telemetry
must not require a bus). SQLite index (rejected: in-memory tail is enough
for one operator and 1 Hz samples).

### 3. Stdlib HTTP + vendored Chart.js

`ThreadingHTTPServer` binds `127.0.0.1:8765` by default (`AGENT_LIVE_PLOT_PORT`
or `--port`; `--host` optional). `GET /` serves package-data HTML that loads
vendored `chart.umd.min.js` from the same origin. Browser polls
`/api/snapshot` every 1s. No CDN. No `webbrowser.open`.

**Alternatives:** matplotlib live GUI (rejected: needs DISPLAY). websockets
extra package (rejected: poll is enough at 1 Hz).

### 4. Wrap lifecycle beside LiveWatcher

Default on for every profile. `--agent-no-live-plot` or `AGENT_LIVE_PLOT=0`
opts out. `--agent-live-plot` forces on. Start in the same `run_user`
wrapper as the OpenCode watcher; print `[agent] live plot: <url>` even when
quiet; stop in `finally`. Inject a fake server in tests.

**Alternatives:** only `agent serve` with no auto-start (rejected: operators
would miss the URL during the job). Keep serving after wrap (rejected:
sidecars follow the job; replay uses `agent serve`).

## Risks / Trade-offs

- [NFS attribute cache delays new JSONL lines] → Accept 1–3s lag; do not add
  a queue in this slice.
- [Many ranks make legends noisy] → Legend click-to-hide; default-visible 48.
- [Port already in use] → Fail-soft collect error; job continues.
- [Vendored Chart.js size] → One minified UMD file in package data.

## Migration Plan

Ship on the submit host with the sidecar tree (`/shared/agent-sidecar`).
No schema change to JSONL. Rollback: `--agent-no-live-plot`; wrap PNG and
telemetry unchanged.

## Open Questions

None. Interval, bind address, and soft cap are specified above.
