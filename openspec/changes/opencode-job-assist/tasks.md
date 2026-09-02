## 1. Live proc-monitor collect (tests first)

- [x] 1.1 Write failing tests that `ProcMonitor.start` with an injected collect loop runs it in the background until `stop()` writes a stop file, and artifacts list `series/*.jsonl`; verify `python3 -m unittest tests.test_proc_monitor` fails
- [x] 1.2 Implement threaded collect loop (keep one-shot `collect_fn` for schema tests); verify `python3 -m unittest tests.test_proc_monitor` passes
- [x] 1.3 Write failing tests that wrap supervisor argv includes `--match` (user binary basename) and `--interval`, and `--agent-match` overrides; verify they fail then implement until `python3 -m unittest tests.test_argv tests.test_cli tests.test_job_assist_profile` pass
- [x] 1.4 Write failing tests that default collect import failure records `mpi_monitor_import` without changing user exit; verify they fail then implement until `python3 -m unittest tests.test_proc_monitor` passes

## 2. Wrap-time PNG (tests first)

- [x] 2.1 Write failing tests that wrap with series files calls an injected plotter and lists returned PNG paths in `evidence_paths`; verify `python3 -m unittest tests.test_wrap_telemetry` fails
- [x] 2.2 Wire `plot_run` after series summary; skip PNG when plotter returns empty; verify `python3 -m unittest tests.test_wrap_telemetry tests.test_plot_optional` pass

## 3. OpenCode job-assist runner (tests first)

- [x] 3.1 Write failing tests that a fake OpenCode runner is invoked once after telemetry for `--agent-profile=job-assist`, prompt contains summary/anomalies/reason_code and not every JSONL line, and `tools-only` invokes zero times; verify `python3 -m unittest tests.test_opencode_assist tests.test_job_assist_profile` fail
- [x] 3.2 Implement injectable `opencode run --dir <repo>` runner; wrap MUST NOT call chat HTTP; verify those tests pass
- [x] 3.3 Write failing tests that successful fake OpenCode writes `assist/job.json` with copied `suspected_reason`, empty `actions`, patches `job_assist`, and does not change `reason_code` or user exit; verify they fail then implement until `python3 -m unittest tests.test_job_assist` passes
- [x] 3.4 Write failing tests that missing binary (`opencode_missing`), timeout (`opencode_timeout`), and non-zero (`opencode_failed`) record collect errors, do not HTTP-fallback, and keep user exit/`reason_code`; verify they fail then implement until `python3 -m unittest tests.test_job_assist tests.test_opencode_assist` pass
- [x] 3.5 Write failing tests that sidecar argv/env strip `ANTHROPIC_*` and `AGENT_LLM_*`; `--agent-node-llm` still unsupported; verify `python3 -m unittest tests.test_job_assist_profile tests.test_cli` pass

## 4. OpenCode docs, skills, launch-fail fixture

- [x] 4.1 Add `agent.md`, `AGENTS.md` (same text), `skills.md`, `.opencode/opencode.json`, and `.opencode/skills/mpi-monitor/` rewritten from ClusterHelm (no workflow_runner / Master / Slave / partition_report); verify files exist and grep shows no `workflow_runner` or `partition_report`
- [x] 4.2 Add launch-failure example plus `scripts/demo_opencode_launch_fail.sh`; update happy-path demo PYTHONPATH to include mpi-monitor src; verify scripts are executable and README documents OpenCode (no keys, no `/home/<user>` paths)

## 5. Suite freeze and NFS retest

- [x] 5.1 Run `python3 -m unittest discover -s tests` and confirm all tests pass
- [x] 5.2 Grep `src/` and `tests/` and confirm wrap does not call chat completions for job-assist, no ClusterHelm workflow imports, no `scancel` remediate helpers, no API keys, sidecar argv does not contain provider keys
- [x] 5.3 Deploy sidecar and mpi-monitor to `/shared`; run happy-path demo (non-empty JSONL, charts PNG, OpenCode note, `reason_code=ok`, exit 0) and launch-fail demo (diagnosis + corrected command, no `scancel`); if `opencode` is missing on mn, install or stop and report — no HTTP fallback

## Out of this change (do not implement)

- SPANK plugin / `plugstack.conf` injector
- Automatic `scontrol` / `scancel` remediation (`--agent-remediate`)
- ClusterHelm adapter (`partition_report`, `workflow_runner`, Master/Slave, submit/wait)
- Per-node LLM / OpenCode (`--agent-node-llm` remains unsupported)
- Cursor CLI / Cursor SDK as the assist runtime
- Silent HTTP fallback when OpenCode is missing
