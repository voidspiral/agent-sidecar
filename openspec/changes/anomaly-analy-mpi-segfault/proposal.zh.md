## 为什么

Wrap 与 `agent analy` 已覆盖 `mpi_abort`，但单 rank 段错误的 stderr
（SIGSEGV / signal 11 / fixture `rank N segfault`）今日会落到
`slurm_failed` 或 `execution_error`，没有专用简体中文分析包。

## 改什么

- 增加 MPI 段错误故障件 `mpi_fault_segfault` 与 demo 脚本。
- 分类器增加 `reason_code=mpi_segfault`。
- 增加确定性 `mpi_segfault` 分析包（阶段 1 索要源码，阶段 2 `--code`），
  接入 `select_pack` / `run_analysis`。
- 增加 OpenCode skill `mpi-segfault` 与 README 说明。
- 本 change 不做 OOM / node_fail / io_stall。

## 能力

### 新能力

- （无 — 复用 `job-analysis`）

### 修改的能力

- `slurm-mpi-classify`：识别段错误相关模式并发出 `mpi_segfault`。
- `job-analysis`：增加 `mpi_segfault` 包场景（对齐 `mpi_abort` 两阶段）。
- `agent-launch`：Wrap / `analy` 将 `mpi_segfault` 路由到专用包；文档化 demo。

## 影响面

- 分类、analysis 包、examples/demo、skill、单元测试（TDD）。

## 非目标

- 多 rank 同时崩、`mpi_signal` 泛化、core dump 解析、OOM/node_fail/io_stall、
  模型改写 `reason_code`、计算节点 OpenCode、自动 `scancel`。
