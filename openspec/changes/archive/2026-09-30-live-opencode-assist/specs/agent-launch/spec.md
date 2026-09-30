## ADDED Requirements

### Requirement: Live submit-host watcher does not replace the PMI step
When job-assist starts a live OpenCode watcher, wrap MUST still launch the user
command as the PMI/PMIx task step. The watcher is a submit-host process (or
child of wrap), not a parent of every rank, and MUST NOT wrap the user step as
`bash -c 'opencode & exec app'`.

#### Scenario: Watcher is extra on the submit host
- **WHEN** job-assist wrap starts overlap supervisors and a live watcher
- **THEN** the user binary remains the SLURM PMI task and OpenCode is not in
  the user `srun` argv

#### Scenario: Watcher stops when wrap ends
- **WHEN** the wrapped user `srun` returns
- **THEN** the live watcher is stopped within the same bounded join as node
  sidecars
