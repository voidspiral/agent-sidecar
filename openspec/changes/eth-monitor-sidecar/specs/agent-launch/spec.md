## ADDED Requirements

### Requirement: NFS deploy includes eth-monitor on PYTHONPATH
`agent deploy` SHALL copy the eth-monitor source tree onto the shared prefix
alongside sidecar and mpi-monitor. Supervisor PYTHONPATH MUST include
`{sidecar}/src`, `AGENT_MPI_MONITOR_SRC` (default `/shared/mpi-monitor/src`),
and `AGENT_ETH_MONITOR_SRC` (default `/shared/eth-monitor/src`). Paths MUST
come from flags or env, not hardcoded user homes. Default skills SHALL
include `eth-monitor`.

#### Scenario: Deploy plans three trees
- **WHEN** `agent deploy --mpi-monitor MPI --eth-monitor ETH` runs
- **THEN** the plan copies eth-monitor to `{shared}/eth-monitor` and prints
  `AGENT_ETH_MONITOR_SRC` plus a PYTHONPATH containing all three `src` dirs

#### Scenario: Missing eth-monitor flag fails closed
- **WHEN** deploy is invoked without an eth-monitor tree
- **THEN** the CLI exits non-zero without copying

#### Scenario: Default skills include eth-monitor
- **WHEN** the user omits `--agent-skills`
- **THEN** supervisor skills include `eth-monitor` in addition to
  proc-monitor, mpi-scan, slurm-tap, and node-diag
