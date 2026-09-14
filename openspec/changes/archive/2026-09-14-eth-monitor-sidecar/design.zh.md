## 背景

见 `proposal.md`。邻居包 `eth-monitor` 已提供 `collect_loop` 和出图。sidecar 目前只 import mpi-monitor，把所有 `*.jsonl` 都当成 pid，live ingest 丢掉没有 `pid` 的样本。用 unittest 做 TDD（先红测）。不引入 ClusterHelm。不硬编码家目录。

## 目标 / 非目标

**目标：**

- 薄 `eth-monitor` 插件，镜像 `ProcMonitor`。
- 三棵树 deploy 与 PYTHONPATH。
- live 以太网两图；wrap PNG 分发；summary 峰值；pid_count 修正。
- job-assist skill 与 standing docs 同步。

**非目标：**

- IB、pcap、网卡抖动触发 live OpenCode、改 mpi-monitor。

## 决策

### 1. 实现方法：TDD

先写失败测试：插件 import 失败、默认 skills、deploy 计划、live ingest 网卡 JSONL、pid_count、plot 不把网卡画成 CPU 图。

### 2. 插件形态

`EthMonitor` 位于 `src/agent_sidecar/tools/eth_monitor.py`，import
`eth_monitor.collect.collect_loop`（测试可注入）。线程 +
`.collect-stop-eth-{host}`。stop 写该文件。artifacts 为 `*_net.jsonl`。
events 恒为 `[]`。

**备选：** 在 sidecar 里刮 `/proc/net`（否定）。

### 3. PYTHONPATH

`sidecar_pythonpath` = `{src}:{mpi}:{eth}`，`AGENT_ETH_MONITOR_SRC` 默认
`/shared/eth-monitor/src`。`agent deploy` 必须给 `--eth-monitor`（或 mpi 后的第二位置参数）。

### 4. Live ingest 拆分

分别 glob `*_pid*.jsonl` 与 `*_net.jsonl`。共享 `t0`。以太网 visible cap 按 rx 峰值。HTML 六张 canvas。

### 5. Plot 分发

`tools/plot.py` 把 `*_net.jsonl` 交给 `eth_monitor.plot.plot_run`（或注入的 plotter）；其余文件仍画四个进程指标。

## 风险 / 权衡

- [NFS 走 IB 时 eth 曲线接近 0] → skill/文档写明这不是 MPI 流量。
- [Deploy CLI 现在必须有 eth-monitor] → 对旧的 `deploy_shared.sh <mpi-dir>` 单参数形式是 **BREAKING**；改为必填第二棵树。

## 迁移计划

运维在 deploy 时传 `--eth-monitor`。作业时缺包 fail-soft。更新 README 示例。

## 未决问题

无。
