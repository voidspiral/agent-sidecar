## Context

See `proposal.md` for motivation. Phase 1 already has `agent srun`, overlap
supervisors, node tools, classifiers, and a wrap-time `telemetry.json` that
only records `exit_code`. `--agent-profile=job-assist` is accepted but ignored.
`--agent-node-llm` prints unsupported. The login host (`mn`) exposes DeepSeek
via `AGENT_LLM_*` (OpenAI-compatible).

Constraints: Python 3.10+; stdlib first; TDD with `unittest` (failing tests
first, then implementation); no network in unit tests; no hardcoded homes;
sidecars follow the job; LLM must not scrape `/proc`; keys stay on the submit
host.

## Goals / Non-Goals

**Goals:**

- Aggregate series and tool artifacts into a complete `JobTelemetry` at wrap
  end, before any model call.
- Invoke one OpenAI-compatible chat completion from the submit host when
  `--agent-profile=job-assist` and credentials are present.
- Persist a `JobAssistNote` without changing `reason_code` or the user exit
  code.

**Non-Goals:**

- Per-node model runtime, SPANK, automatic `scancel`/`scontrol`, ClusterHelm
  adapters, Cursor CLI/SDK as the assist runtime, third-party HTTP SDKs.

## Decisions

### 1. Implementation method: TDD

Write failing `unittest` cases first: fake chat client (no sockets), argv/
profile gating, prompt contents, reason_code preservation, fail-soft HTTP and
timeout, wrap-time summary fields. Then implement until tests pass. Live
DeepSeek probes are optional and gated (`AGENT_LLM_LIVE=1`); they are not
unit tests.

**Alternatives:** calling the real API from unittest (rejected: flaky, leaks
keys, violates "no network in unit tests").

### 2. Assist runs on the submit host after wrap, not in overlap

```
overlap supervisors (tools only, per node)
        │
   user srun (PMI)
        │
   stop sidecar / fetch artifacts
        │
   write JobTelemetry (summary + anomalies + reason_code)
        │
   if profile == job-assist: one chat call on this host
        │
   write assist/job.json, patch telemetry.job_assist
```

Compute nodes never receive `AGENT_LLM_API_KEY` and never issue HTTP to the
provider. `--agent-node-llm` stays a parsed-and-rejected flag.

**Alternatives:** overlap node LLM (rejected: cn often has no egress, 256MiB
budget, key scatter); Cursor CLI (rejected: not a job-lifecycle sidecar).

### 3. Stdlib OpenAI-compatible client

`POST {base}/chat/completions` with `Authorization: Bearer`, JSON body
`{model, messages, temperature: 0}`. Default timeout 30s via
`AGENT_LLM_TIMEOUT`. No `openai` package. Inject a callable in tests.

API key from environment only (never a CLI flag, so it does not appear in
`ps` / SLURM comment). Base URL and model from env, with optional
`--agent-llm-base-url` / `--agent-llm-model` overrides. Empty key → no HTTP,
collect error `llm_unconfigured`.

**Alternatives:** Anthropic Messages API (rejected for this slice: DeepSeek
already works on `/v1`; mn Anthropic vars stay for other tools).

### 4. Wrap-time aggregator reads artifacts, not in-process plugin events

Remote supervisors do not return `events()` to the CLI. After stop, the
launch host:

- `summarize_series(run_dir)` → numeric `summary` (nulls if empty)
- scan `events/` (MPI stderr tail, `slurm.json`, node-diag text) through
  existing classifiers → `anomalies`
- roll up `reason_code`: first tool code if any, else `ok` / `execution_error`
  from the user exit

Then, and only then, job-assist may run. Prompt JSON is
`{summary, anomalies, reason_code, evidence_paths}` and MUST NOT include
series file bodies.

**Alternatives:** serializing plugin events on the node (possible later; not
required if artifacts already classify).

### 5. JobAssistNote schema and telemetry patch

Write `assist/job.json`:

```
host: submit
summary: model text
suspected_reason: copy of tool reason_code
evidence_paths: [...]
confidence: optional
actions: []
```

Force `actions` to `[]` even if the model suggests `scancel`. Re-write
`telemetry.json` adding `job_assist` and the note path; do not change
`reason_code`.

### 6. Fail-soft and exit code

User command exit is returned unchanged. Assist errors
(`llm_unconfigured`, `llm_http`, `llm_timeout`, `llm_parse`) land in
`collect_errors` / extra telemetry. Timeout uses `socket.setdefaulttimeout`
or `urlopen(..., timeout=)`.

## Risks / Trade-offs

- [Key on compute node] → never export `AGENT_LLM_*` into sidecar `srun`.
- [Prompt leaks JSONL] → unit-test the built request; only pass the contract
  dict.
- [Model invents a cause] → `reason_code` copied from telemetry, never from
  model JSON.
- [Provider down / slow] → 30s timeout, fail-soft, user exit preserved.
- [Incomplete artifacts] → empty series yields null summary fields; still
  call the model if profile and credentials are set.
- [ps leaks] → API key env-only.

## Migration Plan

- Existing `tools-only` wraps gain richer `summary`/`anomalies` with no LLM.
- `job-assist` is opt-in. Unset key → collect error, same user exit.
- Rollback: omit `--agent-profile=job-assist` or unset `AGENT_LLM_API_KEY`.
- Do not ship node-LLM or `scancel` stubs.

## Open Questions

- Default model name can remain whatever `AGENT_LLM_MODEL` is on the host
  (`deepseek-v4-flash` on mn today) without baking it into source.
- Whether `agent report` pretty-prints `job_assist` can wait; JSON dump is
  enough for this slice.
