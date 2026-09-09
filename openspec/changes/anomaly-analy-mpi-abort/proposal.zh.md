## Why

本变更解决：wrap 已能把 `MPI_Abort` 分类为 `mpi_abort`，但在
`AGENT_OPENCODE_FINAL_TIMEOUT=0`、活体 OpenCode 随用户步结束而停止时，
常出现有 telemetry、无确定性分析笔记。作业结束后也没有同一套离线复查入口。

## What Changes

- 增加 MPI abort 故障件与演示脚本。
- 确定性 analysis pack：写 `assist/analysis.json`，必要时写中文分条
  `assist/job.json`。
- `agent analy --run-dir`（可选 `--code`、`--llm`）。
- wrap 在非 ok 时调用同一 pack（不依赖 OpenCode）。
- 用户步期间增量刷新 `events/stderr.tail`。
- OpenCode skill `mpi-abort`。
- 扩容路径登记（OOM 后置；node_fail / io_stall 先不做）。

## Capabilities

### New Capabilities
- `job-analysis`：确定性分析 pack 与 `agent analy` 契约。

### Modified Capabilities
- `agent-launch`：`analy` 子命令；wrap 非 ok 调分析。
- `job-telemetry`：分析产物进 evidence；stderr 可中途增长。

## Impact

CLI、wrap/stdio、新包 `analysis/`、示例/demo、OpenCode skill、单测。

## Non-goals

中心库/push、图上框、真宕机/真 Lustre 注入、计算节点 LLM、自动 scancel、
模型自选工具链、`--db=`。
