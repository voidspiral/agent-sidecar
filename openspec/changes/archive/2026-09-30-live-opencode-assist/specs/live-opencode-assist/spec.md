## Purpose

Defines the submit-host live OpenCode watcher: it starts with the user SLURM
step, reads growing tool artifacts (not `/proc`), supports TTY conversation or
non-TTY `--auto` ticks, fail-soft when OpenCode is missing, and stops when the
job ends.

## ADDED Requirements

### Requirement: Live watcher starts with the user step
When job-assist is active, the submitting CLI host SHALL start at most one live
OpenCode watcher when the user `srun` step starts. The watcher MUST run on the
submit host only. Compute nodes MUST NOT run OpenCode. Unit tests MUST inject
the watcher and MUST NOT execute a real `opencode` binary.

#### Scenario: Watcher starts before or with the user step
- **WHEN** `agent srun` wraps a multi-node job under job-assist
- **THEN** a live watcher on the submit host is started by the time the user
  step is running

#### Scenario: No OpenCode on compute nodes
- **WHEN** overlap supervisors start on allocated nodes
- **THEN** those supervisors load only deterministic tools and do not spawn
  OpenCode

### Requirement: Watcher consumes artifact snapshots not raw series
The live watcher MUST use partial numeric summaries, tool `events/`, and
`evidence_paths`. It MUST NOT embed every JSONL sample line and MUST NOT scrape
`/proc` as the primary collector.

#### Scenario: Prompt uses summary not every sample
- **WHEN** series JSONL already contains many lines during the job
- **THEN** a watcher tick's prompt contains a numeric snapshot and anomaly list
  and does not contain every series sample

### Requirement: TTY is interactive and non-TTY is auto
When wrap stdin and stdout are a TTY, the live session SHALL accept operator
questions. When they are not a TTY, the watcher SHALL use non-interactive
`--auto` ticks and MUST NOT block waiting for a prompt.

#### Scenario: Non-TTY demo does not block on stdin
- **WHEN** wrap runs without a TTY (script or CI)
- **THEN** the watcher issues `--auto` ticks and the user step still starts

#### Scenario: TTY allows conversation
- **WHEN** wrap runs on a TTY under job-assist
- **THEN** the operator can send a question to the live session without
  replacing the user PMI step

### Requirement: User srun TTY is not stolen
The live OpenCode session MUST NOT become the parent of, or replace stdin of,
the user `srun` PMI step. If conversation cannot share wrap's TTY without
doing that, wrap MUST keep the user step in the foreground and print how to
attach from a second terminal.

#### Scenario: User step remains the foreground job
- **WHEN** job-assist wrap starts both the watcher and the user `srun`
- **THEN** the user command remains the PMI task step and is not wrapped as
  `bash -c 'opencode & exec app'`

### Requirement: Watcher stops with the job
The live watcher SHALL stop after the user step returns (bounded join). It
MUST NOT remain as a login-host daemon after wrap exits.

#### Scenario: User step end stops the watcher
- **WHEN** the wrapped user `srun` returns
- **THEN** the live watcher is signaled and exits within a bounded join
  timeout

### Requirement: Missing OpenCode is fail-soft during live assist
If `opencode` is not on PATH, live assist MUST record `opencode_missing`, MUST
NOT fall back to HTTP chat, MUST still start node tools and the user command,
and MUST NOT change the user exit code.

#### Scenario: Missing OpenCode still runs the job
- **WHEN** job-assist wrap starts and `opencode` is not on PATH
- **THEN** node sidecars and the user step still run, `opencode_missing` is
  recorded, and the CLI exit code equals the user command's code
