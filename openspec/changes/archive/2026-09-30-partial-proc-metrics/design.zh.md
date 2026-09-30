# sidecar 对部分进程指标的消费

## 背景

mpi-monitor 在 CPU、RSS、读 IO、写 IO 至少一项不为 0 时写样本。缺少 `/proc/<pid>/io` 时，`io_read_bps` 与 `io_write_bps` 为 JSON `null`，并带 `unavailable: ["io"]`。权限失败用 `io_permission`。本仓库原先把缺的速率当成 `0`，会画出贴地的 IO 曲线，看起来像作业没有 I/O。

## 目标

- 汇总、实时叠线、PNG、安静报告和中文结论里，JSON `null` 表示没有这项数据，不是 0。
- `unavailable` 含 `io` 时说明内核未提供 `/proc/<pid>/io`（未打开 `CONFIG_TASK_IO_ACCOUNTING`）。`io_permission` 用另一句。
- 某个指标没有数字点时不写对应 PNG。
- `sample_valid` 与采集端一致：身份字段齐全，且至少一项指标不为 0。

## 非目标

- 不在本仓库读 `/proc`。
- 不用 cgroup 或 Lustre 计数填 `io_*_bps`。
- 不改 `reason_code`、eth-monitor，也不改 job-assist 常驻说明。
