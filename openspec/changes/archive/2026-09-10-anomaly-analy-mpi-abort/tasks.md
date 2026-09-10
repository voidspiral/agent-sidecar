## 1. MPI abort fixture

- [x] 1.1 Add failing/placeholder notes then implement `examples/mpi_fault_abort.c` and update `examples/Makefile`; verify `make -C examples` builds when `mpicc` is available (or document compile in demo)
- [x] 1.2 Add `scripts/demo_mpi_abort.sh` modeled on `demo_job_assist_mpi.sh` with `--agent-match=mpi_fault_abort`; verify script is executable and documents expected `mpi_abort` / `pid_count>0`

## 2. Analysis pack (TDD)

- [x] 2.1 Write failing tests for `run_analysis` on a fixture run_dir with `MPI_Abort` stderr + series; verify `python3 -m unittest tests.test_analysis_pack` fails
- [x] 2.2 Implement `src/agent_sidecar/analysis/` (`mpi_abort` pack, routing, `analysis.json`, conditional `job.json`); verify unittest passes
- [x] 2.3 Write failing tests for `--code` omitted vs present and launch-fail skeleton routing; verify then implement until tests pass

## 3. agent analy CLI (TDD)

- [x] 3.1 Write failing tests for `agent analy --run-dir` / missing flag / `--llm` not called by default; verify fail then implement `cmd_analy` in `cli.py` until pass

## 4. Wrap wiring (TDD)

- [x] 4.1 Write failing tests that wrap with `FINAL_TIMEOUT=0` and MPI abort stdio still writes `assist/analysis.json`; verify fail then wire `wrap_srun` until pass
- [x] 4.2 Write failing tests for incremental `stderr.tail` flush during user step; verify fail then implement flush in `run_user_command` until pass

## 5. OpenCode skill and docs

- [x] 5.1 Add `.opencode/skills/mpi-abort/SKILL.md` and update `.opencode/skills.md`; verify index lists the skill
- [x] 5.2 Update README / README.zh briefly for `agent analy` and demo; verify docs mention `--run-dir` and MPI abort demo

## 6. Expansion (out of this change acceptance)

- [x] 6.1 Document deferred OOM / node_fail / io_stall packs in design only (no implementation in this change); verify design.md expansion section exists
