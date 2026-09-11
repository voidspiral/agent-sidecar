## Context

见 proposal.md 的 Why。当前 `parse_agent_argv` 把 argv[0] 当作启动器，
只消费紧跟其后的 `--agent-*`。公开例子因此长成
`sidecar.sh srun --agent-match=… -n2 -- bin`。`sidecar.sh` 仍是
PYTHONPATH + exec。`sidecar-analy.sh` 已注入 `analy` 并拥有
`--log` / `--code` / `--no-llm`。

约束：Python 3.10+；stdlib 优先；unittest TDD（先失败用例）；无
ClusterHelm；无计算节点 LLM；无写死家目录；`测试.md` 是本 change 的
集群验收脚本。

## Goals / Non-Goals

**Goals:**

- Python 解析器接受 `srun`/`sbatch`/`salloc` 之前的前导 `--agent-*`
  （因此 `sidecar.sh --agent-verbose srun -n2 /path/app` 可用）。
- 用户命令不是选项形态时 `--` 可选。
- 改写 `测试.md` 为新命令；在 mn 上再跑三个真实用例。

**Non-Goals:**

- 在 `sidecar.sh` 里写 getopts。
- 重命名 `--agent-*`。
- 一次性改光所有仍用 `srun --agent-* -- true` 的单测。

## Decisions

1. **实现方法：TDD。** 先在 `tests/test_argv.py` 与
   `tests/test_sidecar_scripts.py` 写失败用例，再改 `parse_agent_argv`。
   单测不 exec 真实 `opencode`。**备选：** bash 把 argv 重排成旧的
   `srun --agent-* …` — 否决；会重复一份 flag 表，且模块 CLI 学不会
   同一套语法。

2. **`sidecar.sh` 仍 thin exec。** 只改用法注释。**备选：** 脚本内
   getopts — 否决（两套解析器）。

3. **前缀 + 后缀旗标。** 先消费前导 `--agent-*`，再要求启动器词，再走
   现有的启动器后循环。**备选：** 丢掉后缀形式 — 否决；单测改动过大。

4. **`--` 可选，仍转发。** `user_command_match` 已回退到第一个非 `-`
   词。文档对绝对路径省略 `--`。**备选：** 始终要求 `--` — 否决；正是
   操作员的抱怨。

5. **验收即 `测试.md`。** unittest 全绿后 rsync 到 `/shared/agent-sidecar`，
   严格按文档跑正常 / abort / segfault（不要夹心 `--agent-match`，不要
   多余 `--`）。

## Risks / Trade-offs

- [`cli.main` 把 argv[0] 特判为 `analy`/`report`] → 前导 `--agent-*`
  只在剩余命令是 SLURM 启动器时生效；`sidecar-analy.sh` 仍先注入
  `analy`。
- [启动器前的 `--` 与 SLURM `--` 混淆] → 仅在启动器前忽略单独 `--`，
  不写进文档。
- [集群 OpenCode 超时] → 仍用 300s 预算；不要设
  `AGENT_OPENCODE_FINAL_TIMEOUT=0`。

## Migration Plan

- 解析器加法；旧 `srun --agent-*` 仍可用。
- 回滚：还原 `argv.py`；脚本仍 thin exec。
- 公开文档和 demo 在本 change 切到前置写法。

## Open Questions

无。
