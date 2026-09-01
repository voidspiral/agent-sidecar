## 1. Package skeleton

- [ ] 1.1 Add `pyproject.toml` (Python ≥3.10, optional `plot` extra, console script `agent` → `agent_sidecar.cli:main`), empty `src/agent_sidecar` package, and `.gitignore` for `__pycache__`, `*.egg-info`, `.venv`; verify `python3 -c "import tomllib, pathlib; tomllib.loads(pathlib.Path('pyproject.toml').read_text())"` succeeds and the script entry is declared
- [ ] 1.2 Add a README that documents `agent srun --agent-profile=tools-only`, `--agent-*` vs SLURM passthrough, and that ClusterHelm control plane is out of scope; verify README mentions `--agent-output-dir` and forbids hardcoded `/home/<user>` paths

## 2. Argv split and profiles (tests first)

- [ ] 2.1 Write failing tests that `--agent-profile`, `--agent-skills`, `--agent-output-dir`, and `--agent-node-llm` are consumed and remaining argv is SLURM; verify `python3 -m unittest tests.test_argv` fails
- [ ] 2.2 Implement argv split; verify `python3 -m unittest tests.test_argv` passes
- [ ] 2.3 Write failing tests that omitted profile is `tools-only`, unknown profile or unknown `--agent-*` exits non-zero, and `--agent-profile=clusterhelm` is rejected; verify they fail then implement until `python3 -m unittest tests.test_profiles` passes

## 3. Supervisor SPI (tests first)

- [ ] 3.1 Write failing tests for plugin `start`/`events`/`stop`/`artifacts` using a fake tool, including idempotent `stop` and anomaly-only `events`; verify `python3 -m unittest tests.test_spi` fails
- [ ] 3.2 Implement supervisor + plugin registry; verify `python3 -m unittest tests.test_spi` passes
- [ ] 3.3 Write failing tests that `(job_id, host)` admits only one supervisor and two skills share that process; verify they fail then implement until `python3 -m unittest tests.test_supervisor_once` passes

## 4. Classification and telemetry schema (tests first)

- [ ] 4.1 Write failing tests mapping SLURM states to `slurm_oom`/`node_fail`/`timeout`/`cancelled`/`slurm_failed` and MPI stderr patterns to `mpi_abort`; verify `python3 -m unittest tests.test_classify` fails
- [ ] 4.2 Implement classifiers; verify `python3 -m unittest tests.test_classify` passes
- [ ] 4.3 Write failing tests that `telemetry.json` contains `summary`, `anomalies`, `evidence_paths`, `reason_code`, and that application non-zero sets `retry_allowed` false while overlap-fail-before-start sets true with `attempt` 1; verify they fail then implement until `python3 -m unittest tests.test_telemetry` passes
- [ ] 4.4 Write failing tests for run layout `telemetry.json`/`meta.json`/`series/`/`assist/` with no hardcoded home paths; verify they fail then implement until `python3 -m unittest tests.test_run_layout` passes

## 5. Launch injection (tests first, stub launcher)

- [ ] 5.1 Write failing tests that the default plan is overlap `--ntasks-per-node=1 --mem=256M` plus a separate user `srun`, and that `bash -c '… & exec …'` is never the user step; verify `python3 -m unittest tests.test_launch_plan` fails
- [ ] 5.2 Implement launch planner with a stub `srun`; verify `python3 -m unittest tests.test_launch_plan` passes
- [ ] 5.3 Write failing tests that overlap failure before the user command triggers exactly one exec-wrapper fallback and records it in telemetry; verify they fail then implement until `python3 -m unittest tests.test_launch_fallback` passes
- [ ] 5.4 Write failing tests that CLI exit code equals the wrapped command and collect errors do not replace it; verify they fail then implement until `python3 -m unittest tests.test_exit_code` passes

## 6. Node tools (tests first)

- [ ] 6.1 Write failing tests that `proc-monitor` delegates to mpi-monitor collect schema (`ts`,`host`,`pid`,`cpu_pct`,`rss_mb`,`io_*`) and excludes launchers; verify `python3 -m unittest tests.test_proc_monitor` fails (mock mpi-monitor)
- [ ] 6.2 Implement `proc-monitor` adapter; verify `python3 -m unittest tests.test_proc_monitor` passes
- [ ] 6.3 Write failing tests for `mpi-scan` on fixture stderr (`MPI_Abort` vs clean log) and `slurm-tap` on fixture `scontrol`/`sacct` text; verify they fail then implement until `python3 -m unittest tests.test_mpi_scan tests.test_slurm_tap` pass
- [ ] 6.4 Write failing tests for `node-diag` OOM/cgroup fixtures inspired by memmon/nodestatus techniques (no ClusterHelm imports); verify they fail then implement until `python3 -m unittest tests.test_node_diag` passes
- [ ] 6.5 Write failing tests that missing matplotlib skips PNG and leaves JSONL; verify they fail then implement until `python3 -m unittest tests.test_plot_optional` passes

## 7. Fetch, node-assist notes, CLI wiring (tests first)

- [ ] 7.1 Write failing tests that local-temp artifacts are copied to the launch run dir and a fetch timeout records a per-host collect error without hanging; verify `python3 -m unittest tests.test_fetch` fails
- [ ] 7.2 Implement bounded fetch (srun/SSH helpers mocked); verify `python3 -m unittest tests.test_fetch` passes
- [ ] 7.3 Write failing tests that non-model `node-assist` writes `NodeAssistNote` under `assist/` from local artifacts and never invokes `scancel`/`scontrol`; verify they fail then implement until `python3 -m unittest tests.test_node_assist` passes
- [ ] 7.4 Write failing tests for `agent sbatch` env export without rewriting the script body; verify they fail then implement until `python3 -m unittest tests.test_sbatch_env` passes
- [ ] 7.5 Implement `agent` CLI (`srun`/`sbatch`/`salloc`/`supervisor`/`report`) with flags only; verify `python3 -m unittest tests.test_cli` passes

## 8. Full suite and phase-1 freeze

- [ ] 8.1 Run `python3 -m unittest discover -s tests` and confirm all tests pass
- [ ] 8.2 Grep `src/` and `tests/` and confirm no `/home/smt`, `/home/cn1`, ClusterHelm workflow imports, `scancel` remediate helpers, or SPANK plugin sources exist in this change

## Out of phase 1 (do not implement)

- SPANK plugin / `plugstack.conf` injector
- Automatic `scontrol` / `scancel` remediation (`--agent-remediate`)
- ClusterHelm adapter (`partition_report`, `workflow_runner`, Master/Slave, submit/wait)
- Per-node LLM runtime (`--agent-node-llm` may be parsed and rejected or recorded as unsupported)
- Job-assist model loop (formatting stub only if needed for telemetry tests)
