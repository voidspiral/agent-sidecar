## Why

Operators still mix sidecar flags (`--agent-verbose`, `--agent-match`) into
the `srun` argv, plus an extra `--` before the user binary. HPC users
need the SLURM tail to look like native `srun`, with sidecar options
owned by `sidecar.sh` / `sidecar-analy.sh`.

## What Changes

- Preferred wrap grammar: `sidecar.sh [--agent-*] srun <native slurm> <user>`.
  The same leading `--agent-*` form works for `python3 -m agent_sidecar`.
- A lone `--` between SLURM options and an absolute-path user binary is
  **not required**. If the operator still writes `--`, it is forwarded to
  SLURM unchanged.
- `--agent-match` is omitted when the user binary basename already
  matches (proc-monitor default). Override remains available as a
  `sidecar.sh` flag **before** `srun`.
- `sidecar-analy.sh --log DIR --code PATH` is unchanged (options already
  sit on the script).
- **Not BREAKING:** `srun --agent-* <slurm>` after the launcher remains
  accepted so existing unit tests keep working. Public docs and
  `测试.md` use the prefix form only.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `agent-launch`: wrap argv accepts leading `--agent-*` before `srun` /
  `sbatch` / `salloc`; `--` is optional when the user command is not
  option-shaped; public operator commands put sidecar flags on the
  wrapper scripts.

## Impact

- Parser: [`src/agent_sidecar/argv.py`](src/agent_sidecar/argv.py)
- Script usage comments: `scripts/sidecar.sh` (still PYTHONPATH + exec)
- Operator acceptance: `测试.md` (three real cases)
- README EN/ZH, demos, pack suggestion strings, deploy footer examples
- Tests: `tests/test_argv.py`, `tests/test_sidecar_scripts.py` (TDD)

## Non-goals

- ClusterHelm control-plane integration (Master/Slave, workflow_runner,
  partition_report, SPANK, auto `scancel`).
- Unwrapped native `srun` without `sidecar.sh` (SPANK / prolog).
- Renaming `--agent-verbose` to `--verbose`.
- Duplicating flag parsing in bash getopts.
- Changing `sidecar-analy.sh` / `agent analy` flag names.
- Inventing `reason_code` or compute-node LLM.
