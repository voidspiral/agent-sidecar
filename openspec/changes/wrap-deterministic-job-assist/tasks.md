## 1. Failing tests

- [ ] 1.1 Wrap job-assist default (`AGENT_OPENCODE_FINAL_TIMEOUT` unset): OpenCode runner call count is 0; `assist/job.json` exists with numbered 简体中文 including a 建议 item; `job_assist` listed on telemetry. Verify `python3 -m unittest tests.test_job_assist_profile tests.test_job_assist` fail
- [ ] 1.2 Resource-hint unit tests: exit 0 + pid_count 0 mentions match; low cpu_peak with pids; high cpu_peak; ethernet NIC disclaimer; no JSONL bodies. Verify `python3 -m unittest tests.test_resource_hints` fail
- [ ] 1.3 Pack `job.json` kept when wrap has mpi_abort and timeout unset; runner not called. Positive FINAL_TIMEOUT still calls OpenCode. `timeout=0` still writes hints. `agent analy --llm` still calls OpenCode. Verify those tests fail

## 2. Implementation

- [ ] 2.1 Add `src/agent_sidecar/analysis/resource_hints.py` and wire `run_job_assist` precedence: live → existing job.json → hints; OpenCode only if FINAL_TIMEOUT > 0. Verify the tests in 1. pass
- [ ] 2.2 Keep `run_analysis(..., use_llm=True)` unlink behavior for analy. Verify `python3 -m unittest tests.test_analy_cli tests.test_analysis_pack` pass

## 3. Docs

- [ ] 3.1 Sync English/Chinese standing job-assist docs and README wrap OpenCode paragraphs. Verify `python3 -m unittest tests.test_agents_md_sync` plus `python3 -m unittest discover -s tests` pass

## Out of phase 1

- SPANK injector
- Automatic remediate (`scancel` / `scontrol`)
- ClusterHelm adapter
