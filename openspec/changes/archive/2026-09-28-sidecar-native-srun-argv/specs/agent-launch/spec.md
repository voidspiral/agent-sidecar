## ADDED Requirements

### Requirement: Sidecar flags precede the SLURM launcher
The wrap CLI SHALL accept known `--agent-*` flags before the launcher
word (`srun`, `sbatch`, or `salloc`) and MUST NOT forward those flags to
SLURM. `sidecar.sh [--agent-*] srun <slurm> <user>` is the preferred
operator form. The same leading-flag grammar MUST work for
`python3 -m agent_sidecar`. Known `--agent-*` immediately after the
launcher MUST remain accepted. An unrecognized `--agent-*` MUST still
fail closed before launching SLURM.

#### Scenario: Flags on sidecar.sh before srun
- **WHEN** the operator runs `sidecar.sh --agent-verbose srun -n 2 /path/app`
- **THEN** SLURM receives `-n 2 /path/app` (or equivalent) and does not
  receive `--agent-verbose`

#### Scenario: Module CLI leading flags
- **WHEN** the operator runs `python3 -m agent_sidecar --agent-profile=tools-only srun -n 1 ./app`
- **THEN** the profile is `tools-only` and SLURM passthrough is `-n 1 ./app`

#### Scenario: Trailing agent flags still work
- **WHEN** the operator runs `sidecar.sh srun --agent-verbose -n 1 hostname`
- **THEN** verbose is enabled and SLURM receives `-n 1 hostname`

#### Scenario: Unknown leading agent flag fails closed
- **WHEN** the operator runs `sidecar.sh --agent-nope srun -n 1 hostname`
- **THEN** the CLI exits non-zero with an error on stderr before launching SLURM

### Requirement: End-of-options dash-dash is optional
When the user command does not begin with `-`, the wrap CLI MUST accept
passthrough without a `--` separator. If `--` is present in the SLURM
passthrough, the CLI MUST forward it to SLURM. Public operator docs MUST
omit `--` for absolute-path example binaries.

#### Scenario: Absolute path without dash-dash
- **WHEN** the operator runs `sidecar.sh srun -n 2 /shared/agent-sidecar/examples/mpi_io_load 15 /shared/mpi-io 0`
- **THEN** SLURM passthrough is `-n 2` plus that binary and its arguments,
  and does not require `--`

#### Scenario: Operator-supplied dash-dash is forwarded
- **WHEN** the operator runs `sidecar.sh srun -n 1 -- python3 -c 'print(1)'`
- **THEN** SLURM receives the `--` token in passthrough
