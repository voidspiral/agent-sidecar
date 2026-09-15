## 为什么

Live overlay 和 wrap 后的 PNG 已经能画 CPU/RSS/IO/以太网曲线，但已分类的
故障（`mpi_abort`、`mpi_segfault`、`slurm_oom`、`node_local`）从不出现在
时间轴上。运维看不到已知工具事件相对曲线落在何时。abort 那次 change 把
图框列为非目标；现在补上这一刀。

## 改什么

- 为现有四类点事件记录首次检测的 Unix epoch `ts`。
- 在 `events/` 下按主机 append-only 写 marker JSONL，live 与 wrap 绘图不自行
  解析 stderr/dmesg。
- 把可选 `ts` 合并进 `telemetry.anomalies`，不改变 `reason_code` 汇总顺序。
- 在 live Chart.js 六张图和 wrap matplotlib PNG（进程与 eth/TCP）上画竖线
  和 host/`reason_code` 标签框。
- 健康 CPU/以太网抖动仍不得变成 marker，也不得触发 live OpenCode。模型保持
  纯文本，不得看 PNG 像素。

## 非目标

- 不接入 ClusterHelm 控制面（Master/Slave、`workflow_runner`、
  `partition_report`、`run-slave.sh`、submit/wait、gateway preflight）。
- 不做模型看图识异常。
- 不因健康序列触发 live OpenCode。
- 不做 P2 持续检测器（`cpu_idle` 等）或阴影区间。
- 不改变主 `reason_code` 选取。
- 不调用 `scancel`/`scontrol`，不加新的 pip/CDN Chart.js 插件。
- 不伪造比首次检测更精确的故障时刻。
