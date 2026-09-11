## 1. Parser TDD

- [x] 1.1 Write failing tests in `tests/test_argv.py`: `--agent-verbose srun -n 2 /abs/app 15 /shared/mpi-io 0` consumes verbose, passthrough has no sidecar flags and need not contain `--`; `--agent-profile=tools-only srun -n 1 ./app` works; `srun --agent-verbose -n 1 hostname` still works; `--agent-nope srun …` raises. Verify `python3 -m unittest tests.test_argv` fails
- [x] 1.2 Write failing test in `tests/test_sidecar_scripts.py` that `sidecar.sh` usage comment is `sidecar.sh [--agent-*] srun <slurm> <user>` and does not document flags after `srun`. Verify that test fails

## 2. Parser implementation

- [x] 2.1 Implement leading `--agent-*` in `parse_agent_argv` (then launcher, then existing after-launcher loop). Verify `python3 -m unittest tests.test_argv tests.test_sidecar_scripts` pass
- [x] 2.2 Update `scripts/sidecar.sh` usage comment only (still PYTHONPATH + exec). Verify the script test from 1.2 passes

## 3. Operator docs and demos

- [x] 3.1 Rewrite `测试.md` three cases: sidecar flags before `srun` (or omitted), no extra `--`, no in-srun `--agent-match`; analy stays `sidecar-analy.sh --log … --code`. Verify the three wrap lines match the change scenarios
- [x] 3.2 Align README.md / README.zh.md, demo scripts, pack suggestion strings, and deploy footer examples with the same grammar. Verify `python3 -m unittest tests.test_analysis_pack tests.test_deploy` still pass if those strings are asserted
- [x] 3.3 Run `python3 -m unittest discover -s tests` and verify the suite is green

## 4. Cluster acceptance

- [x] 4.1 Rsync the tree to `mn:/shared/agent-sidecar` and compile examples with `CC=mpicc make`. Verify binaries exist on `/shared/agent-sidecar/examples/`
- [x] 4.2 Run the three cases from the updated `测试.md` on `cn1,cn3` (`unset AGENT_OPENCODE_FINAL_TIMEOUT`). Verify healthy `reason=ok` + Chinese `assist/job.json`; abort `mpi_abort` + `--code` hits `mpi_fault_abort.c`; segfault `mpi_segfault` + hit includes `:51`

## 5. Out of phase 1

- [x] 5.1 SPANK, automatic remediate, and ClusterHelm adapter remain out of this change; verify they are listed only under Non-goals (no implementation tasks)
