# Skills

Index only. OpenCode loads each skill from `.opencode/skills/<name>/SKILL.md`.

| Skill | When to use |
|-------|-------------|
| [mpi-monitor](skills/mpi-monitor/SKILL.md) | CPU/RSS/IO JSONL under `series/`, optional PNG under `charts/`, collect via overlap supervisor |
| [launch-fail](skills/launch-fail/SKILL.md) | `execution_error` with `pid_count=0` / missing executable / ENOENT |
| [node-diag](skills/node-diag/SKILL.md) | `node_local` / job-scoped OOM killer / cgroup `oom_kill` / NFS hang |

Standing instructions (keep in sync): [`AGENTS.md`](AGENTS.md),
[`agent/job-assist.md`](agent/job-assist.md),
[`.cursor/rules/job-assist.mdc`](../.cursor/rules/job-assist.mdc).
Chinese: [`AGENTS.zh.md`](AGENTS.zh.md).
