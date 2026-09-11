## 1. Analy CLI flags (TDD)

- [x] 1.1 Write failing tests in `tests/test_analy_cli.py`: missing `--log`/`--run-dir` exits non-zero; `--log DIR` works; `--no-llm` skips OpenCode; default `--log DIR` invokes mocked `run_opencode_assist`; conflicting `--log`/`--run-dir` fails. Verify `python3 -m unittest tests.test_analy_cli` fails
- [x] 1.2 Implement `cmd_analy` (`--log` alias, default `use_llm=True`, `--no-llm`) until those tests pass; verify unittest passes

## 2. Pack ask_code_cmd and quiet report (TDD)

- [x] 2.1 Write failing tests that phase-1 `ask_code_cmd` / Chinese notes contain `sidecar-analy.sh --log` (not module `--run-dir --llm`); verify `python3 -m unittest tests.test_analysis_pack` fails then update packs until pass
- [x] 2.2 Write failing quiet-report test that non-ok `reason_code` adds a `sidecar-analy.sh --log` next-step line; verify fail then implement `format_run_report` until `tests.test_quiet_report` passes

## 3. sidecar.sh tools-only default (TDD)

- [x] 3.1 Write failing tests that `AGENT_ENTRY=sidecar` with omitted `--agent-profile` yields `tools-only`, explicit `--agent-profile=job-assist` wins, and unset `AGENT_ENTRY` leaves module default unchanged; verify `python3 -m unittest tests.test_sidecar_scripts` (or argv tests) fails
- [x] 3.2 Implement `apply_profile_defaults` + `scripts/sidecar.sh` / `scripts/sidecar-analy.sh` (PYTHONPATH, `AGENT_ENTRY=sidecar`, exec module); verify scripts are executable and tests pass
- [x] 3.3 Print both `/shared/agent-sidecar/scripts/sidecar.sh` and `sidecar-analy.sh` in deploy import-check footer; verify deploy tests or string assertion pass

## 4. Docs and demos

- [x] 4.1 Lead README.md / README.zh with the two scripts; keep module CLI as advanced; verify both mention `sidecar.sh srun` and `sidecar-analy.sh --log`
- [x] 4.2 Update demo scripts and OpenCode skills / standing job-assist copies that cite `agent analy --run-dir`; verify `python3 -m unittest tests.test_agents_md_sync` stays green if standing docs change
- [x] 4.3 Run `python3 -m unittest discover -s tests` and verify the suite is green

## 5. Out of phase 1

- [x] 5.1 SPANK, automatic remediate, and ClusterHelm adapter remain out of this change; verify they are listed only under Non-goals (no implementation tasks)
