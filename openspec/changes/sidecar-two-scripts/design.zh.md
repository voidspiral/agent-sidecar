## Context

见 proposal.md（Why）。现入口是 `python3 -m agent_sidecar srun` 与
`agent analy --run-dir`（`--llm` 可选）。quiet wrap 已打印
`run: {run_dir}`。pack 的 `ask_code_cmd` 仍指向模块 analy。模块 CLI 省略
`--agent-profile` 的默认值本 change 不改（避开 live-opencode-assist）。

约束：Python 3.10+；stdlib 优先；unittest TDD（先失败测试）；注入
OpenCode runner；无 ClusterHelm；无计算节点 LLM；无写死用户家目录；
`--log` 是 sidecar run 目录，不是裸 SLURM 日志。

## Goals / Non-Goals

**Goals:**

- 两条登录节点脚本：`sidecar.sh`（跑/采）与 `sidecar-analy.sh`（分析，默认 LLM）。
- `AGENT_ENTRY=sidecar` 在省略 profile 时选 tools-only。
- `--log` / `--run-dir` 别名；`--no-llm` 做确定性 analy。
- 下一步文案用 `sidecar-analy.sh --log`。

**Non-Goals:**

- 改 `agent srun` 省略 profile 的行为。
- 裸 `.out` 摄入、`sidecar.sh` wrap 期 LLM、ClusterHelm。

## Decisions

1. **实现方法：TDD。** CLI、`AGENT_ENTRY`、脚本、report 下一步先写失败
   unittest，再实现。单测不执行真实 `opencode`。**备选：** bash 插入
   `--agent-profile=tools-only` — 否决（难单测）。

2. **`sidecar.sh` 做薄 PATH 包装。** 解析仓库根、把 `src/` 加进
   `PYTHONPATH`、导出 `AGENT_ENTRY=sidecar`、exec
   `python3 -m agent_sidecar "$@"`。profile 默认放在
   `apply_profile_defaults`。**备选：** bash 改写 argv — 否决。

3. **模块 `agent srun` 的 profile 不变。** 仅 `AGENT_ENTRY=sidecar` 把省略
   profile 打成 tools-only。显式 `--agent-profile` 优先。**备选：** 全局默认
  改成 tools-only — 否决，避免和 live-opencode-assist 打架。

4. **`agent analy` 默认 OpenCode。** `--no-llm` 才是确定性路径；`--llm`
   仍接受。wrap 仍 `run_analysis(..., use_llm=False)`。缺 OpenCode 仍
   fail-soft。**备选：** 保持 `--llm` 可选 — 否决；分析入口应默认用模型。

5. **`--log` 是 `--run-dir` 别名。** 同一 Path；两者都给且不等 → 退出 2。
   对外文档和 `ask_code_cmd` 用 `--log`。**备选：** 删掉 `--run-dir` — 否决。

6. **Quiet report 下一步：** `reason_code != ok` 时一行
   `sidecar-analy.sh --log {run_dir} --code /path/to/src`。

7. **Deploy 页脚** 打印 `/shared/agent-sidecar/scripts/sidecar.sh` 与
   `sidecar-analy.sh`（整树已经 rsync）。

## Risks / Trade-offs

- [仍用 `agent srun` 会在 wrap 期跑 OpenCode] → 文档以 `sidecar.sh` 为对外入口。
- [默认 analy OpenCode 卡住 CI] → 单测注入 runner；禁止 exec 真二进制；确定性测试用 `--no-llm`。
- [`--log` 与 `--run-dir` 冲突] → 失败关闭。
- [rsync 后脚本无执行位] → git 里 `+x`；测试断言可执行。

## Migration Plan

- 脚本可加；`--run-dir` 与 `--llm` 仍可用。
- 回滚：不用新脚本；不想默认 OpenCode 则传 `--no-llm`。
- Demo 优先新脚本；live job-assist 显式 `--agent-profile=job-assist`。

## Open Questions

无。`--log` 含义与 wrap/analy 的 LLM 分工已在 proposal 锁定。
