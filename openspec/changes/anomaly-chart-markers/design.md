## Context

See `proposal.md` for motivation. Production anomalies come from scanning
`events/` (`stderr.tail`, `slurm.json`, `node-diag.txt`), not from
serializing `spi.Event`. Live Chart.js overlays six metrics from JSONL;
wrap matplotlib writes per-pid PNGs and delegates eth/TCP PNGs to
`eth_monitor.plot.plot_run`. Neither path has a timestamped marker contract.
`Supervisor.events()` is unused on the wrap path. Constraints: Python 3.10+,
stdlib first, matplotlib optional, TDD with `unittest`, no Selenium, no CDN,
no ClusterHelm.

## Goals / Non-Goals

**Goals:**

- Persist first-seen detection time for four point codes and draw it on live
  and wrap charts.
- Keep `reason_code` rollup and live-OpenCode gating unchanged.

**Non-Goals:**

- Duration boxes, P2 classifiers, eth-monitor repo edits, Chart.js annotation
  packages, inventing a fault instant finer than first detection.

## Decisions

### 1. Implementation method: TDD

Write failing `unittest` cases first (marker JSONL, first-seen dedupe,
telemetry merge, live `x = ts - t0`, HTML contains afterDraw, matplotlib
`axvline` spy, out-of-range skip). Then implement until those tests pass.
No real browser, no live `/proc`, no real `srun` in unit tests.

**Alternatives:** Selenium screenshots (rejected: flaky). Pixel PNG diffs
(rejected: backend-dependent).

### 2. Per-host append-only marker JSONL

New helper records `{ts, reason_code, message, evidence_path, host}` to
`events/{host}_markers.jsonl` (submit host: `events/submit_markers.jsonl`).
Dedup key `(reason_code, evidence_path, host)` keeps the first `ts`.
MPI abort/segfault are recorded from submit-host `run_user_command` flushes
of `events/stderr.tail` (the live path). `slurm-tap` / `node-diag` record on
first emit using `ctx.host`. Only the four chart codes are stored.

**Alternatives:** One shared `events/markers.jsonl` (rejected: NFS multi-node
writers). Embedding `ts` only inside `slurm.json` (rejected: stderr.tail
overwrite and node-diag refresh would lose first-seen). Using file mtime
(rejected: NFS). Wiring production through `Supervisor.events()` (rejected:
not on the wrap path).

### 3. Optional anomaly `ts`, unchanged rollup

`anomalies_from_artifacts` keeps the current scan order and dict shape.
When a marker matches `(reason_code, evidence_path)` it copies `ts`.
Old runs omit `ts`. `rollup_reason_code` still uses `anomalies[0]`.

**Alternatives:** Sort anomalies by `ts` (rejected: would change primary
`reason_code` for existing fixtures).

### 4. Live: relative `x`, hand-drawn Chart.js plugin

Ingest tails `*_markers.jsonl` by byte offset. Snapshot adds `markers`
with `x = ts - t0`. If there is no series `t0`, still return markers (empty
metrics) without failing. HTML `afterDraw` draws a vertical line and a
label box (`host` + `reason_code`) on all six charts. No extra JS vendor.

**Alternatives:** `chartjs-plugin-annotation` (rejected: extra vendor file
and CDN risk). Shaded ranges (deferred to P2 duration events).

### 5. Wrap PNG: absolute epoch axis, inject eth writer

Process `_default_plotter` keeps absolute `ts` on X and calls `axvline` /
text for in-range markers. Eth/TCP charts get the same via
`eth_monitor.plot.plot_run(..., writer=...)` so the neighbor package is
unchanged. Markers outside `[min(xs), max(xs)]` are skipped. Missing
matplotlib still skips PNG.

**Alternatives:** Convert wrap PNG to elapsed seconds (rejected: visual
break vs existing PNGs). Post-process PNG bytes (rejected: lossy).

## Risks / Trade-offs

- [Detection `ts` is later than the true fault] → Document as first-seen;
  stderr flush already happens during the user step.
- [Submit MPI markers use host `submit`] → Label shows `submit mpi_abort`;
  still aligns on the shared elapsed axis.
- [NFS delay on new marker lines] → Accept 1s live poll lag.
- [`_anomaly_hash` includes new `ts`] → Hash only changes when a new
  first-seen marker appears, which is the desired live re-tick.

## Migration Plan

Ship with `/shared/agent-sidecar`. Old run directories without marker files
keep current charts. Rollback is a tree revert; JSONL series schema is
unchanged.

## Open Questions

None. Marker codes, file layout, relative vs absolute axes, and rollup
order are specified above.
