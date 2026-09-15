## 背景

动机见 `proposal.md`。生产路径的异常来自扫描 `events/`（`stderr.tail`、
`slurm.json`、`node-diag.txt`），并不序列化 `spi.Event`。Live Chart.js 用
JSONL overlay 六张图；wrap matplotlib 写 per-pid PNG，以太网/TCP PNG 委托
`eth_monitor.plot.plot_run`。两条路径都没有带时间戳的标注契约。
`Supervisor.events()` 不在 wrap 生产路径上。约束：Python 3.10+，标准库优先，
matplotlib 可选，TDD `unittest`，无 Selenium/CDN/ClusterHelm。

## 目标 / 非目标

**目标：**

- 为四类点事件落下首次检测时间，并画在 live 与 wrap 图上。
- 不改变 `reason_code` 汇总和 live OpenCode 门控。

**非目标：**

- 持续区间框、P2 分类器、改 eth-monitor 仓库、Chart.js annotation 包、
  伪造比首次检测更精确的故障时刻。

## 决策

### 1. 实现方法：TDD

先写失败 unittest（marker JSONL、首次去重、telemetry 合并、live
`x = ts - t0`、HTML afterDraw、matplotlib `axvline` spy、越界跳过），再实现
直到通过。单元测试不开真浏览器、不刮 live `/proc`、不跑真 `srun`。

**备选：** Selenium 截图（否决：不稳）；PNG 像素对比（否决：后端相关）。

### 2. 每主机 append-only marker JSONL

新 helper 把 `{ts, reason_code, message, evidence_path, host}` 写到
`events/{host}_markers.jsonl`（提交端 `events/submit_markers.jsonl`）。
去重键 `(reason_code, evidence_path, host)` 保留首次 `ts`。MPI abort/segfault
在提交端 `run_user_command` 刷新 `stderr.tail` 时记录（live 主路径）。
`slurm-tap` / `node-diag` 在首次 emit 时用 `ctx.host` 记录。只存四类图表码。

**备选：** 共用一个 `markers.jsonl`（否决：NFS 多写者）；只把 `ts` 塞进
`slurm.json`（否决：stderr/node-diag 覆盖会丢首次时间）；用 mtime（否决：
NFS）；生产路径改走 `Supervisor.events()`（否决：不在 wrap 路径上）。

### 3. 可选 anomaly `ts`，汇总顺序不变

`anomalies_from_artifacts` 保持现有扫描顺序和 dict 形状。marker 按
`(reason_code, evidence_path)` 匹配则拷贝 `ts`。旧 run 省略 `ts`。
`rollup_reason_code` 仍用 `anomalies[0]`。

**备选：** 按 `ts` 排序 anomalies（否决：会改现有 fixture 的主 `reason_code`）。

### 4. Live：相对 `x`，手写 Chart.js 插件

按字节 offset tail `*_markers.jsonl`。snapshot 增加 `markers`，`x = ts - t0`。
没有 series `t0` 时仍返回 markers、不失败。HTML `afterDraw` 在六张图画竖线和
`host`+`reason_code` 标签框。不加新的 JS vendor。

**备选：** `chartjs-plugin-annotation`（否决：额外 vendor/CDN 风险）；阴影区间
（留给 P2 持续事件）。

### 5. Wrap PNG：绝对 epoch 轴，注入 eth writer

进程 `_default_plotter` 保持绝对 `ts` 横轴，对范围内 marker 调用 `axvline`/文本。
以太网/TCP 通过 `eth_monitor.plot.plot_run(..., writer=...)` 用同一 writer，
不改邻居包。`ts` 落在 `[min(xs), max(xs)]` 之外则跳过。无 matplotlib 仍跳过 PNG。

**备选：** wrap PNG 改成相对秒（否决：破坏既有图语义）；二次处理 PNG 字节
（否决：有损）。

## 风险 / 权衡

- [检测 `ts` 晚于真实故障] → 文档化为 first-seen；stderr 已在用户步内 flush。
- [提交端 MPI marker 的 host 是 `submit`] → 标签为 `submit mpi_abort`，仍对齐
  共享已运行时间轴。
- [NFS 延迟新 marker 行] → 接受 1s live 轮询滞后。
- [`_anomaly_hash` 含新 `ts`] → 只有新的首次 marker 才会改 hash，这正是
  live 需要再 tick 的情况。

## 迁移

随 `/shared/agent-sidecar` 发布。没有 marker 文件的旧 run 保持现图。回滚即
回退树；series JSONL schema 不变。

## 未决问题

无。marker 码、文件布局、相对/绝对轴、汇总顺序均已定。
