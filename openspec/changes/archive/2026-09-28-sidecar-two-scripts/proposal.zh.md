## Why

现在包装作业要用 `python3 -m agent_sidecar srun`，复查要用
`agent analy --run-dir` 且 `--llm` 是可选。HPC 用户需要两条登录节点
shell 入口：先跑作业，再事后授权源码并用模型解读（默认开 LLM）。

## What Changes

- Add `scripts/sidecar.sh` wrapping `srun`/`sbatch`/`salloc`. 省略
  `--agent-profile` 时仍为 `job-assist`：每次 wrap（含正常作业）都用节点
  工具产物在提交端跑 OpenCode。`--agent-profile=tools-only` 为关闭开关。
- 增加 `scripts/sidecar-analy.sh`，包装 `agent analy`。
- **BREAKING**（`agent analy`）：默认开 OpenCode。`--no-llm` 回到纯确定性。
  `--llm` 仍接受。
- `agent analy` 用 `--log DIR` 作为 sidecar run 目录的对外名字。`--run-dir`
  兼容别名。二者必具其一；冲突则失败。
- 阶段 1 `ask_code_cmd` 与 quiet report 下一步指向
  `sidecar-analy.sh --log … --code …`。
- deploy import-check 页脚打印 `/shared` 上这两条脚本路径。

## Capabilities

### New Capabilities

- （无）

### Modified Capabilities

- `agent-launch`：登录节点 `sidecar.sh` / `sidecar-analy.sh`；wrap 默认
  `job-assist`；analy 接受 `--log` 或 `--run-dir`。
- `job-analysis`：`agent analy` 默认 OpenCode；`--no-llm` 为确定性路径；
  `ask_code_cmd` 写成 `sidecar-analy.sh --log`。

## Impact

脚本、CLI、profile 默认、pack/report/deploy、README/demo/skills、单测。

## Non-goals

ClusterHelm 控制面、裸 SLURM/应用日志当 `--log`、用 `analy` 替代伴随启动的
job-assist 总结、计算节点 LLM、自动 remediate、编造 `reason_code`。
