## 1. JSONL overlay ingest

- [x] 1.1 Write failing tests that two JSONL files overlay on `cpu_pct` with distinct host/pid/rank legend ids, append increases point count, and empty `series/` returns empty lists; verify `python3 -m unittest tests.test_live_plot` fails
- [x] 1.2 Implement byte-offset tail, 900-point downsample, and 48-trace `visible` metadata in `live_plot.py`; verify `python3 -m unittest tests.test_live_plot` passes

## 2. HTTP UI and agent serve

- [x] 2.1 Write failing tests that `GET /` contains canvases and `GET /api/snapshot` returns overlay JSON for a fixture run_dir; verify `python3 -m unittest tests.test_live_plot_http` fails
- [x] 2.2 Implement stdlib HTTP server, vendored Chart.js page (four overlay charts), package data, and `agent serve --run-dir`; verify `python3 -m unittest tests.test_live_plot_http tests.test_cli` pass

## 3. Wrap lifecycle

- [x] 3.1 Write failing tests that an injected live-plot server starts before `run_user`, stops after, quiet prints `live plot:`, bind failure records `collect_errors.live_plot` without changing user exit or `reason_code`, and `--agent-no-live-plot` skips start; verify they fail then implement until `python3 -m unittest tests.test_live_plot_wrap tests.test_argv` pass

## 4. Docs (phase 1; no ClusterHelm adapter, no SPANK, no automatic remediate)

- [x] 4.1 Update README (EN/ZH) and `.opencode/skills/mpi-monitor/SKILL.md` so wrap PNG stays per-pid while the live UI overlays by metric; mention `ssh -L` and `--agent-no-live-plot`; verify `python3 -m unittest tests.test_agents_md_sync` still passes
