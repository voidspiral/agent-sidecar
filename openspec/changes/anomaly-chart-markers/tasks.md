## 1. Marker contract (tests first)

- [ ] 1.1 Write failing tests that `Event` accepts optional `ts`, `record_marker` writes `events/{host}_markers.jsonl` / `submit_markers.jsonl`, duplicate `(reason_code, evidence_path, host)` keeps the first `ts`, and unknown codes are ignored; verify `python3 -m unittest tests.test_spi tests.test_chart_markers` fail
- [ ] 1.2 Implement `Event.ts` and the marker helper; verify `python3 -m unittest tests.test_spi tests.test_chart_markers` pass

## 2. Record first-seen events and merge telemetry

- [ ] 2.1 Write failing tests that stderr flush records `mpi_abort`/`mpi_segfault` once, `slurm-tap` records `slurm_oom` on first emit, `node-diag` records `node_local` once, `anomalies_from_artifacts` copies `ts` when markers exist and omits `ts` on old runs, and rollup order is unchanged; verify `python3 -m unittest tests.test_wrap_telemetry tests.test_slurm_tap tests.test_node_diag tests.test_plugin_abnormal` fail
- [ ] 2.2 Wire wrap flush, slurm-tap, node-diag, and mpi-scan recording plus telemetry merge; verify those tests pass and `reason_code` is unchanged

## 3. Live overlay markers

- [ ] 3.1 Write failing tests that snapshot `markers[].x` is `ts - t0`, empty marker files yield `[]`, append appears later, no-series snapshot still includes markers, and `GET /` HTML draws marker lines without a CDN annotation plugin; verify `python3 -m unittest tests.test_live_plot tests.test_live_plot_http` fail
- [ ] 3.2 Implement ingest + Chart.js afterDraw on all six charts; verify those tests pass

## 4. Wrap PNG markers

- [ ] 4.1 Write failing tests that in-range markers call `axvline` on process PNGs, out-of-range markers are skipped, eth/TCP writer injection draws the same codes, and no-marker / no-matplotlib paths keep JSONL; verify `python3 -m unittest tests.test_plot_optional tests.test_plot_markers` fail
- [ ] 4.2 Implement matplotlib annotation and eth-monitor writer injection (do not patch the eth-monitor repo); verify those tests pass

## 5. Docs and regression (no SPANK, no automatic remediate, no ClusterHelm adapter)

- [ ] 5.1 Mention marker JSONL and chart overlays in README EN/ZH and mpi-monitor / node-diag skills without telling the model to read PNG pixels; verify `python3 -m unittest tests.test_agents_md_sync` passes
- [ ] 5.2 Run `python3 -m unittest discover -s tests` and confirm healthy series still do not emit markers
