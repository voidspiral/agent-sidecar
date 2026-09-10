## 1. MPI segfault fixture

- [ ] 1.1 Add `examples/mpi_fault_segfault.c` and update `examples/Makefile`; verify `make -C examples` builds when `mpicc` is available (or document compile in demo)
- [ ] 1.2 Add `scripts/demo_mpi_segfault.sh` with `--agent-match=mpi_fault_segfault`; verify script is executable and documents expected `mpi_segfault` / `pid_count>0`
- [ ] 1.3 Gitignore example binaries (`mpi_fault_*`, `mpi_io_load`) under `examples/`

## 2. Classify (TDD)

- [ ] 2.1 Write failing tests for `mpi_segfault` patterns (fixture line, Segmentation fault, SIGSEGV, signal 11) and abort orthogonality; verify `python3 -m unittest tests.test_classify tests.test_mpi_scan tests.test_plugin_abnormal` fails
- [ ] 2.2 Implement `MPI_PATTERNS` in `classify.py`; verify those tests pass

## 3. Analysis pack (TDD)

- [ ] 3.1 Write failing tests for `run_analysis` on a segfault fixture run_dir (phase-1 no line cites; phase-2 `--code`); verify `python3 -m unittest tests.test_analysis_pack` fails
- [ ] 3.2 Implement `mpi_segfault` pack and wire `packs.py` / `runner.py`; verify unittest passes
- [ ] 3.3 Optional wrap stdio capture test for segfault → `analysis.json`; verify until pass

## 4. OpenCode skill and docs

- [ ] 4.1 Add `.opencode/skills/mpi-segfault/SKILL.md` and update skill index if present
- [ ] 4.2 Update README / README.zh for segfault demo and skill; verify docs mention `mpi_segfault`
