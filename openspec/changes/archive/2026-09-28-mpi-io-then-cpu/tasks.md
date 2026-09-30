## 1. Tests first

- [x] 1.1 Write failing unittest that `examples/mpi_io_load.c` documents
      `cpu_seconds` as argv3, unlinks the scratch file before the CPU
      phase, and rank-0 logs IO-done plus CPU-done; verify
      `python3 -m unittest tests.test_mpi_io_load_example` fails
- [x] 1.2 If `mpicc` is available, add a compile-and-run case for
      `1s IO + 1s CPU` that asserts those stderr markers and exit 0
      (gated by `AGENT_TEST_MPI_COMPILE=1` so CI does not pin a core)

## 2. Implement the two-phase example

- [x] 2.1 Extend `examples/mpi_io_load.c`: parse argv3 (default 30, 0 skips
      CPU), close/unlink, `MPI_Barrier`, volatile 1 MiB CPU burn, rank-0
      phase logs; keep `mpi_io_load [io_seconds] [work_dir]` working
- [x] 2.2 Verify `python3 -m unittest tests.test_mpi_io_load_example` passes

## 3. Docs and demo

- [x] 3.1 Update README.md / README.zh.md, `scripts/demo_job_assist_mpi.sh`
      (`AGENT_MPI_CPU_SECONDS`, default 30), and launch-fail skill example
      argv comment
- [x] 3.2 Run `python3 -m unittest discover -s tests`

## Out of this change (do not implement)

- mpi-monitor `rchar` vs `read_bytes`
- live overlay / Chart.js axis changes
- job-assist prompt changes
- ClusterHelm adapters, `scancel` / `scontrol`
