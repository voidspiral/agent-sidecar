# design.md 中文翻译

## 背景

见 proposal（Why）。现有 wrap 能从 stderr 分类 MPI abort 并写 telemetry；
FINAL_TIMEOUT=0 时常跳过 post-job OpenCode；无离线 analy CLI。

## 目标 / 非目标

**目标：** 共享 `run_analysis`；首包 `mpi_abort`；故障件+demo；stderr 增量 flush。

**非目标：** SQLite/`--db`、push、图框；OOM/node_fail/io_stall 不作为本 change 验收
（路由可留 stub）。

## 决策

1. TDD；单测不 exec 真 opencode。
2. 始终写 `analysis.json`；仅当无 `job.json` 时才写，避免冲掉 live promote。
3. `agent analy` 默认确定性；`--llm` 才调 OpenCode。
4. `--code` 显式授权、只读、限额。
5. wrap 非 ok 调 pack（`use_llm=False`）。
6. stderr 按字节阈值中途 flush，退出再最终写。
7. 扩容：OOM 后置；node_fail / io_stall 先不做（无真 reboot / 无真 Lustre hang）。

## 风险

过早 abort 误判 launch-fail → 故障件先工作数秒。pack 与 LLM 冲突 → 不覆盖已有 job.json。

## 迁移

纯增量；回滚去掉 analy / demo 即可。
