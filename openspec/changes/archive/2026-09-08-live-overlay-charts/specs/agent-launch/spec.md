## ADDED Requirements

### Requirement: Submit-host live plot follows the user step
When live plot is enabled, wrap SHALL start a submit-host HTTP overlay server
before or with the user step and MUST stop it when the user step returns.
The server MUST NOT appear in the user `srun` argv and MUST NOT run on
compute nodes. `--agent-no-live-plot` MUST skip the server. Bind failure
MUST NOT replace the user command exit code.

#### Scenario: Live plot starts before the user command
- **WHEN** wrap runs with live plot enabled
- **THEN** the overlay server start happens before `run_user` and stop happens
  after the user step returns

#### Scenario: Quiet mode prints the plot URL
- **WHEN** quiet wrap starts the overlay server successfully
- **THEN** stderr or stdout includes a `live plot:` URL

#### Scenario: Bind failure is fail-soft
- **WHEN** the overlay port cannot be bound
- **THEN** the user command still runs and the CLI exit code remains the
  user command's code
