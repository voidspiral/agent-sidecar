## 1. Wrap-time telemetry aggregation (tests first)

- [x] 1.1 Write failing tests that wrap-end `telemetry.json` `summary` includes `cpu_avg`, `cpu_peak`, `rss_peak_mb`, IO fields, `host_count`, and `pid_count` from `series/` (nulls when empty); verify `python3 -m unittest tests.test_wrap_telemetry` fails
- [x] 1.2 Implement wrap-time `summarize_series` into `write_telemetry`; verify `python3 -m unittest tests.test_wrap_telemetry` passes
- [x] 1.3 Write failing tests that `events/` MPI stderr and `slurm.json` become `anomalies` and set authoritative `reason_code` before any assist; verify they fail then implement until `python3 -m unittest tests.test_wrap_telemetry tests.test_classify` pass

## 2. LLM config and fake client (tests first)

- [x] 2.1 Write failing tests that `AGENT_LLM_BASE_URL` / `AGENT_LLM_API_KEY` / `AGENT_LLM_MODEL` load from env, `--agent-llm-base-url` and `--agent-llm-model` override, and there is no `--agent-llm-api-key` flag; verify `python3 -m unittest tests.test_llm_config` fails
- [x] 2.2 Implement config parsing (env + flags, key env-only); verify `python3 -m unittest tests.test_llm_config tests.test_argv` pass
- [x] 2.3 Write failing tests for a fake chat client: request JSON contains `summary`/`anomalies`/`reason_code`, does not embed series JSONL lines, and uses `POST .../chat/completions`; verify `python3 -m unittest tests.test_llm_client` fails
- [x] 2.4 Implement stdlib OpenAI-compatible client with injectable transport; verify `python3 -m unittest tests.test_llm_client` passes

## 3. JobAssistNote and fail-soft (tests first)

- [x] 3.1 Write failing tests that a successful fake response writes `assist/job.json` with copied `suspected_reason`, empty `actions`, and no `scancel`/`scontrol` invocation; verify `python3 -m unittest tests.test_job_assist` fails
- [x] 3.2 Implement `JobAssistNote` writer (force `actions: []`); verify `python3 -m unittest tests.test_job_assist` passes
- [x] 3.3 Write failing tests that missing key (`llm_unconfigured`), HTTP error (`llm_http`), timeout (`llm_timeout`), and parse failure (`llm_parse`) record collect errors, do not change `reason_code`, and do not change the user exit code; verify they fail then implement until `python3 -m unittest tests.test_job_assist` passes

## 4. Profile wiring (tests first)

- [x] 4.1 Write failing tests that `--agent-profile=job-assist` with credentials issues exactly one fake chat call after telemetry exists, and `tools-only` issues zero; verify `python3 -m unittest tests.test_job_assist_profile` fails
- [x] 4.2 Wire `wrap_srun` / CLI to run job-assist once on the submit host; never export `AGENT_LLM_*` into sidecar argv; verify `python3 -m unittest tests.test_job_assist_profile tests.test_cli` pass
- [x] 4.3 Write failing tests that `--agent-node-llm` still starts no node model and is recorded unsupported; verify they fail then implement until `python3 -m unittest tests.test_job_assist_profile` passes
- [x] 4.4 Write failing tests that successful assist patches `telemetry.json` with `job_assist` and the note path in `evidence_paths` without changing `reason_code`; verify they fail then implement until `python3 -m unittest tests.test_job_assist_profile` passes

## 5. Docs, suite freeze

- [x] 5.1 Document `--agent-profile=job-assist` and `AGENT_LLM_*` in README (no keys, no `/home/<user>` paths); verify README mentions job-assist and env vars
- [x] 5.2 Run `python3 -m unittest discover -s tests` and confirm all tests pass
- [x] 5.3 Grep `src/` and `tests/` and confirm no API keys, no ClusterHelm workflow imports, no `scancel` remediate helpers, no SPANK sources, and sidecar argv does not contain `AGENT_LLM_API_KEY`

## Out of this change (do not implement)

- SPANK plugin / `plugstack.conf` injector
- Automatic `scontrol` / `scancel` remediation (`--agent-remediate`)
- ClusterHelm adapter (`partition_report`, `workflow_runner`, Master/Slave, submit/wait)
- Per-node LLM runtime (`--agent-node-llm` remains unsupported)
- Cursor CLI / Cursor SDK as the assist runtime
- Live DeepSeek unittest (optional gated probe only, not a required task)
