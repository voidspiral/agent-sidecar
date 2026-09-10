## 背景

见 proposal（Why）。`mpi_abort` 包与 `agent analy` / wrap 已存在；分类器
目前只匹配 abort 族 stderr，单 rank 空指针段错误不会被标为专用 MPI 码。

## 目标 / 非目标

**目标：**

- 故障件 `mpi_fault_segfault`：先 busy，再指定 rank 空指针写，并打印
  `rank N segfault (null deref)`。
- 分类 `mpi_segfault`（fixture 行 + 常见 launcher 文案）。
- 分析包 `mpi_segfault`，阶段 1/2 合同对齐 `mpi_abort`。
- Demo 与 OpenCode skill。

**非目标：** 多 rank 同时崩、`mpi_signal`、core dump、OOM/node_fail/io_stall
验收。

## 决策摘要

1. TDD；CI 用合成 stderr，集群 demo 验证真机文案。
2. code 名 `mpi_segfault`，与 abort 正交。
3. Fixture 自写 stderr 行为 demo 权威证据；launcher 正则作补充。
4. 用空指针写触发，不用 `MPI_Abort` / `raise`。
5. 复用现有 `run_analysis` 两阶段规则。
6. OOM 后置；node_fail / io_stall 仍延后。

## 风险

- launcher 文案差异 → 多正则 + fixture 行保底。
- 过早崩溃无采样 → fixture 先工作若干秒。

## 迁移

仅增量；回滚去掉 pattern/pack/demo 即可。
