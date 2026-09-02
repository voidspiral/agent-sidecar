## 背景

动机见 `proposal.md`。本仓库在 OpenSpec 脚手架之外仍为空。相邻仓库
`mpi-monitor` 作为进程采集/绘图库被调用。ClusterHelm 中的工具实现
（`memmon.py`、nodestatus 探测手法）只用于启发 `node-diag`。ClusterHelm
控制面不是设计输入。

约束：Python 3.10+；标准库优先；matplotlib 可选；计算节点可能未安装本包；
禁止硬编码家目录；TDD（`unittest`，先写失败测试再实现）。Sidecar 跟随
SLURM 作业生命周期。LLM 不得作为 `/proc` 的主采集器。

## 目标 / 非目标

**目标：**

- 提供作业级 `agent` CLI，主路径为 `agent srun`。
- 注入每节点一个 supervisor（默认 overlap step，回退 exec-wrapper），加载确定性工具插件。
- 产出 `JobTelemetry` 以及 series/charts；可选 `NodeAssistNote`。
- 远程采集无需预装（内联 payload、`srun` 回传或 SSH）。

**非目标：**

- SPANK、仅 TaskProlog 注入、自动 `scontrol`/`scancel` 修正。
- ClusterHelm 适配（`partition_report`、`workflow_runner`、Master/Slave）。
- 节点常驻守护进程、以 PMPI 作为主采样器、Grafana。

## 决策

### 1. 两条正交轴：启动 vs 布置

启动回答 sidecar 如何随 SLURM 起来。布置回答起来之后节点上跑什么。一期实现
启动模型 A+C（B 为回退），以及布置 P1（`tools-only`）加上无模型的 P2
`NodeAssistNote`。P3 作业级 LLM 写入规格，但第一实现切片推迟。

**备选：** 把布置折进启动器（否决：overlap 与 exec-wrapper 不得按 rank 拉起节点 LLM）。

### 2. 实现方法：TDD

先写失败的 `unittest`：argv 拆分（`--agent-*` vs SLURM）、supervisor 唯一性、
插件 SPI 替身、telemetry 模式、reason-code 映射、用桩启动器测 overlap 与回退。
再实现直到测试通过。真实 SLURM 测试可选且需门禁。单元测试不访问网络。

### 3. 包布局与 CLI 表面

```
src/agent_sidecar/     # 库：argv、启动、supervisor、插件、telemetry
tests/                 # unittest
pyproject.toml         # console script `agent`
```

CLI：

- `agent srun [--agent-profile=...] [--agent-skills=...] [--agent-output-dir DIR] [srun-args] -- CMD...`
- `agent sbatch` / `agent salloc`（导出环境并透传）
- `agent supervisor --job-id ID --host HOST --output-dir DIR --skills LIST`
- `agent report --run-dir DIR`（从产物生成/打印 telemetry）

只用 flags 与配置文件。禁止 `/home/<user>/...` 字面量。

**备选：** 仅提供 `python -m`（体验差于 `agent srun`）；每个 skill 一个子进程（被 sidecar-spi 否决）。

### 4. 默认注入：overlap step，然后 exec-wrapper

默认：

```
srun --overlap --ntasks-per-node=1 --exact --mem=256M agent supervisor ...
srun <用户参数>   # PMI 在这一步
```

若 overlap 在用户命令启动前失败，则重试一次 exec-wrapper：fork 采集器，
父进程 `execve` 用户二进制，使 PMI pid 为应用。node-assist 必须保持每节点
一个进程，而不是每个 rank 一个。

**备选：** SPANK（二期）；TaskProlog（需管理员、每 rank 执行、有 drain 风险）；
`srun bash -c 'mon & exec app'`（禁止；破坏 PMI 且过量拉起）。

### 5. Supervisor SPI 与一期工具

每个 (`SLURM_JOB_ID`, host) 一个 supervisor。插件实现 `start`、`events`、
`stop`、`artifacts`。

| 工具 | 职责 | 来源 |
|------|------|------|
| `proc-monitor` | PID CPU/RSS/IO JSONL | 调用 `mpi-monitor` collect |
| `slurm-tap` | `scontrol`/`sstat`/`sacct` | 本仓库 |
| `mpi-scan` | stderr 模式库 | 本仓库 |
| `node-diag` | 本地 OOM/cgroup/文件系统信号 | 按 memmon/nodestatus 手法重写 |
| `plot` | 可选 PNG | `mpi-monitor` plot |

事件只报异常。用户 step 退出码不得被采集错误替换。

### 6. 布置剖面

- `tools-only`（默认）：supervisor + 工具，无 LLM。
- `node-assist`：每主机一个只读诊断器；必须带 `--agent-node-llm` 才起模型。
  写 `NodeAssistNote`。禁止 `scancel`/`scontrol`。
- `job-assist`：整个 allocation 一个 `JobTelemetry` 消费者。若 P2 与 P3 同时
  运行，只有 job-assist 或提交端 CLI 可以重试。

一期实现 tools-only 与无模型 node-assist。job-assist 可以先做不调用模型、
只格式化 telemetry 的桩。

### 7. JobTelemetry 与传输

运行目录：

```
{output_dir}/{run_id}/
  telemetry.json
  meta.json
  series/{host}_pid{pid}.jsonl
  charts/                  # 可选
  events/
  assist/                  # NodeAssistNote
```

`telemetry.json` 包含 `summary`、`anomalies`、`evidence_paths`、`reason_code`，
以及可选的 `node_assist`、`retry_allowed`、`attempt`。协助层读该文档，而不是
原始 JSONL。

无共享盘：写入 `$TMP/agent-sidecar/{job_id}/{host}/`，停止后通过 `srun`、SSH
或 mpi-monitor 式内联 payload 拉取。拉取有超时；失败记入 collect errors。

### 8. 先分类，再 LLM

`slurm-mpi-classify` 映射 SLURM 状态（`slurm_oom`、`node_fail`、`timeout`、
`cancelled`、`slurm_failed`）、MPI 模式（`mpi_abort`）以及序列/节点阈值
（`cpu_idle`、`mem_overalloc`、`rank_imbalance`、`io_stall`、`node_local`）。
阈值来自 flags/配置。仅在应用启动前的、已文档化的瞬时注入/启动器失败时，
`retry_allowed` 为 true。

### 9. 非 SLURM 回退

当没有 `srun` 时，`agent srun` 必须失败退出，除非用户显式传入
`--agent-launcher=`（例如 `mpirun`）以及 `--hosts`。该路径把进程 wrap 委托给
`mpi-monitor wrap`，仍写 `JobTelemetry`。这是兼容舱口，不是 SLURM 主路径。

## 风险 / 权衡

- [站点关闭 overlap] → 文档化的一次 exec-wrapper 回退；记入 telemetry；禁止按 rank 的 bash。
- [PMIx 假设 task pid] → 优先 overlap，保持用户 `srun` 不变；exec-wrapper 仅作回退测试。
- [Sidecar 抢核] → `--exact --mem=256M --ntasks-per-node=1`；节点 LLM 为独立 opt-in step。
- [无共享盘 / 缺少 python3] → 内联 payload + 有界拉取；按主机记录错误；CLI 退出码仍为用户命令。
- [短作业、1s 间隔] → 继承 mpi-monitor `--interval`；允许空序列。
- [计算节点上的 LLM] → 默认关闭；作业结束 SIGTERM；默认不申请 GPU。

## 迁移计划

- 新仓库：无生产迁移。unittest 通过后打标签。
- 在提交主机安装 CLI；计算节点需要 `python3` 与 `/proc`。
- 回滚：停止用 `agent` 包装；残留 supervisor 随作业结束。
- SPANK 与自动修正留待后续 change；不要提供调用 `scancel` 的桩。

## 未决问题

- 配置文件格式（`toml` vs 仅 flags）可延后；v1 用 flags 即可。
- idle/imbalance 的具体默认数值可在实现测试中给定，不必改规格。
- 站点上 `agent` 控制台脚本是否重名，属于安装期选择（必要时增加
  `agent-sidecar` 额外脚本名）。
