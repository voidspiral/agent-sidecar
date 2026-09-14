## 1. Plugin and default skills

- [ ] 1.1 Write failing tests that default skills include `eth-monitor` and missing import writes `events/eth_monitor_import.err`; verify `python3 -m unittest tests.test_plugin_abnormal tests.test_argv` fails
- [ ] 1.2 Implement `EthMonitor` plugin, register it, append default skills, and verify those tests pass

## 2. Deploy and PYTHONPATH

- [ ] 2.1 Write failing tests that deploy requires `--eth-monitor`, plans `/shared/eth-monitor`, and PYTHONPATH has three entries; verify `python3 -m unittest tests.test_deploy` fails
- [ ] 2.2 Implement deploy/run PYTHONPATH and `deploy_shared.sh`; verify `python3 -m unittest tests.test_deploy` passes

## 3. Live overlay, summary, PNG

- [ ] 3.1 Write failing tests for net JSONL overlay, process charts uncontaminated, pid_count ignoring net files, eth peaks; verify `python3 -m unittest tests.test_live_plot tests.test_wrap_telemetry` fails
- [ ] 3.2 Implement live ingest/HTML, `summarize_series`, plot dispatch; verify those tests pass

## 4. Docs and job-assist

- [ ] 4.1 Add `.opencode/skills/eth-monitor`, sync English/Chinese standing docs and README, and verify `python3 -m unittest tests.test_agents_md_sync` plus `python3 -m unittest discover -s tests` pass
