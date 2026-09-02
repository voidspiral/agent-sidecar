## 1. Default profile job-assist (tests first)

- [x] 1.1 Write failing tests that omitted `--agent-profile` is `job-assist` and `--agent-profile=tools-only` skips OpenCode; verify `python3 -m unittest tests.test_profiles tests.test_argv` fail
- [x] 1.2 Flip `AgentOptions.profile` default to `job-assist`; verify those tests pass
- [x] 1.3 Write failing tests that omitted profile still starts overlap tools and attempts submit-host assist; verify they fail then implement until `python3 -m unittest tests.test_job_assist_profile tests.test_cli` pass

## 2. Live watcher (tests first)

- [ ] 2.1 Write failing tests for an injected `LiveWatcher` (`start` / `tick` / `stop`) that `tick` prompt uses a numeric snapshot and events, not every JSONL line, and `stop` is idempotent; verify `python3 -m unittest tests.test_live_opencode` fails
- [ ] 2.2 Implement watcher with snapshot hash skip and `AGENT_OPENCODE_LIVE_INTERVAL` (default 15s); missing OpenCode records `opencode_missing` without HTTP fallback; verify `python3 -m unittest tests.test_live_opencode tests.test_opencode_assist` pass
- [ ] 2.3 Write failing tests that non-TTY wrap starts the watcher before `run_user`, uses `--auto`, does not read stdin, and `stop` runs after the user step; verify they fail then implement until `python3 -m unittest tests.test_job_assist_profile` passes
- [ ] 2.4 Write failing tests that TTY wrap prints an attach hint on stderr, does not put OpenCode on user `srun` argv/stdin, and still ticks `--auto`; verify they fail then implement until `python3 -m unittest tests.test_live_opencode tests.test_cli` pass

## 3. Final note and telemetry (tests first)

- [ ] 3.1 Write failing tests that live files under `assist/` do not overwrite `reason_code`, and the final OpenCode note still runs after `telemetry.json`; verify they fail then implement until `python3 -m unittest tests.test_job_assist tests.test_wrap_telemetry` pass
- [ ] 3.2 Keep sidecar `env -u` of `ANTHROPIC_*` / `AGENT_LLM_*`; `--agent-node-llm` still unsupported; verify `python3 -m unittest tests.test_job_assist_profile tests.test_cli` pass

## 4. Docs and demos

- [ ] 4.1 Update `.opencode/AGENTS.md` / `.opencode/agent/job-assist.md` / `.cursor/rules/job-assist.mdc` for during-job snapshot analysis (still no `/proc` scrape, no compute OpenCode); verify copies stay in sync (`python3 -m unittest tests.test_agents_md_sync`) and grep shows no `workflow_runner` or `partition_report`
- [ ] 4.2 Update README / README.zh.md shortest `agent srun` (no required `--agent-profile=job-assist`); drop the flag from demos; verify scripts stay executable and mention `tools-only` as the off switch
- [ ] 4.3 Update `openspec/config.yaml` context so default placement is job-assist; verify the file still validates as YAML

## 5. Suite freeze

- [ ] 5.1 Run `python3 -m unittest discover -s tests` and confirm all tests pass
- [ ] 5.2 Grep `src/` and `tests/` and confirm wrap does not call chat completions, no ClusterHelm workflow imports, no `scancel` remediate helpers, no OpenCode in sidecar argv

## Out of this change (do not implement)

- SPANK plugin / `plugstack.conf` injector
- Automatic `scontrol` / `scancel` remediation (`--agent-remediate`)
- ClusterHelm adapter (`partition_report`, `workflow_runner`, Master/Slave, submit/wait)
- Per-node LLM / OpenCode (`--agent-node-llm` remains unsupported)
- Required tmux/screen split as the injector
- Silent HTTP fallback when OpenCode is missing
- Cursor CLI / Cursor SDK as the assist runtime
