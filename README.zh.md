# agent-sidecar

SLURM 作业生命周期 sidecar。用本 CLI 包装 `srun`：分配一起步，每节点拉起一个
sidecar，采样进程 CPU/RSS/IO，分类 SLURM/MPI/节点故障，写出 `JobTelemetry`。
作业结束 sidecar 随之退出。

这不是 ClusterHelm。Master/Slave、`workflow_runner`、`partition_report` 均不在
本仓库范围内。

英文版见 [README.md](README.md)。

## 安装

```bash
pip install -e .
# 可选 PNG 图
pip install -e ".[plot]"
```

需要 Python 3.10+。输出目录来自 `--agent-output-dir`、`AGENT_JOB_DIR` 或相对
run 目录。不要写死 `/home/<user>/...`。

未 `pip install` 时可用模块方式：

```bash
export PYTHONPATH=/path/to/agent-sidecar/src
python3 -m agent_sidecar srun -- ...
```

## 包装作业

`--agent-*` 由本 CLI 消费，**不会**转发给 SLURM。

```bash
agent srun --agent-output-dir ./runs -N 2 -n 4 -- ./app
```

默认 `--agent-profile` 为 `job-assist`（节点工具 + 提交端 OpenCode）。
`--agent-skills` 默认为 `proc-monitor,mpi-scan,slurm-tap,node-diag`；有 `/shared` 时输出目录默认为
`/shared/agent-runs`；默认为 `--agent-quiet`（关键步骤 + 最终 report）。
`--agent-verbose` 打开完整启动痕迹。`--agent-profile=tools-only` 关闭 OpenCode。

| 参数 | 含义 |
|------|------|
| `--agent-profile` | `job-assist`（默认）、`tools-only`（无 OpenCode）、`node-assist` |
| `--agent-skills` | 节点 sidecar 加载的工具，逗号分隔 |
| `--agent-output-dir` | run 目录的父路径（或设 `AGENT_JOB_DIR`） |
| `--agent-verbose` | 打印 overlap sidecar / 用户 step 的启动过程 |
| `--agent-quiet` | 只打关键步骤，结束时写出紧凑 `report.txt`（header、job-assist、metrics、hosts、证据计数；也可用 `AGENT_QUIET=1`） |
| `--agent-node-llm` | 可选节点模型；记录为不支持 |
| `--agent-match` | 覆盖 proc-monitor 的 `--match`（默认用用户二进制基名） |
| `--agent-interval` | 采样间隔秒（默认 `1.0`） |
| `--agent-live-plot` / `--agent-no-live-plot` | 提交端叠线 HTTP（默认开）。`AGENT_LIVE_PLOT=0` 关闭；`AGENT_LIVE_PLOT_PORT` 改端口（默认 `8765`） |

`job-assist`（默认）在提交端跑 OpenCode：**仅当 `events/` 出现工具异常**时做
live 解读（`opencode run --dir <本仓库>`），不再 `POST /chat/completions`，不 source
任何供应商 env 文件，也不在计算节点上跑模型。OpenCode 用登录节点上自己的
配置。进程环境里若已有供应商变量，会从 sidecar `srun` 剥掉。缺少 `opencode`
时 **不会** 回退 HTTP。

```bash
# 在 mn 上；凭据留在 OpenCode 自己的配置里，不要拷到计算节点或 git

python3 -m agent_sidecar srun -N 2 -n 4 -- ./app
```

缺少 OpenCode 或 runner 失败写入 `collect_errors`（`opencode_missing` /
`opencode_timeout` / `opencode_failed`），不替换用户退出码，也不改
`reason_code`。

`proc-monitor` 会 `import mpi_monitor.collect.collect_loop`。把 sidecar 和
**mpi-monitor 源码树** 一起放到 NFS，计算节点才能采集 CPU/RSS/IO。mpi-monitor
默认路径是 `/shared/mpi-monitor/src`，可用 `AGENT_MPI_MONITOR_SRC` 覆盖。

```bash
# 在 mn 上；参数是你的 mpi-monitor 目录（仓库根或 src/）
bash scripts/deploy_shared.sh /path/to/mpi-monitor
# 只打印路径，不拷贝
bash scripts/deploy_shared.sh --dry-run /path/to/mpi-monitor
# 等价
python3 -m agent_sidecar deploy --mpi-monitor /path/to/mpi-monitor
```

脚本会 rsync 本仓库到 `/shared/agent-sidecar`、给定目录到
`/shared/mpi-monitor`，并打印 `AGENT_MPI_MONITOR_SRC` 与 `PYTHONPATH`。
`agent srun` 会自动把该路径注入 overlap supervisor，作业里不必再 export
`PYTHONPATH`。缺包是 fail-soft：写 `events/mpi_monitor_import.err`，`series/`
为空，不改用户退出码。

有 matplotlib 时 wrap 会在 `charts/` 写出 **每个 pid × 指标** 一张 PNG。
作业运行期间，提交端还会起 live overlay 页（同一指标下所有进程叠在一张图，
图例用 rank 或 `host pid`）。quiet 会打印
`[agent] live plot: http://127.0.0.1:8765`。笔记本访问：
`ssh -L 8765:127.0.0.1:8765 mn`。结束后回放：

```bash
python3 -m agent_sidecar serve --run-dir /shared/agent-runs/<run_id>
```

`--agent-no-live-plot` 或 `AGENT_LIVE_PLOT=0` 关闭。端口占用只记
`collect_errors.live_plot`，不改用户退出码。

可选：设 `AGENT_OPENCODE_MODEL`（`provider/model`）固定模型。job-assist
live 超时默认 300s（`AGENT_OPENCODE_TIMEOUT`）。用户步骤结束时取消 live
OpenCode；若已有 `assist/live.json` 摘要则提升为 `assist/job.json`。
除非设置 `AGENT_OPENCODE_FINAL_TIMEOUT` 大于 0，作业结束后不再新拉一轮模型。

MPI 示例见 `examples/mpi_io_load.c`：每 rank 先约 60 秒 NFS 写/fsync/读，
再 30 秒本地 CPU burn（`mpi_io_load [io_seconds] [work_dir] [cpu_seconds]`；
第三参数传 `0` 则跳过 CPU）。本集群 NFS 挂在
`/shared`（`mn:/shared`）。源码、二进制、IO scratch 和 run 产物都放这里，
各节点同一份文件：

```bash
# 在 mn 上
bash scripts/deploy_shared.sh /path/to/mpi-monitor
bash /shared/agent-sidecar/scripts/demo_job_assist_mpi.sh \
  /shared/agent-sidecar /shared/agent-runs
```

启动失败（故意缺失二进制）给 OpenCode 诊断：

```bash
bash /shared/agent-sidecar/scripts/demo_opencode_launch_fail.sh
```

作业把每 rank 文件写到 `/shared/mpi-io`（可用 `AGENT_MPI_WORKDIR` 覆盖）。
OpenCode 凭据留在登录节点 OpenCode 自己的配置里，不上 NFS、不进本仓库。

常驻说明放在工具目录（作业协助 LLM 是 OpenCode，Cursor 只做本地调试）：
`.opencode/AGENTS.md`、`.opencode/agent/job-assist.md`、
`.cursor/rules/job-assist.mdc`。中文：`.opencode/AGENTS.zh.md`。
OpenCode skills：`.opencode/skills/`（索引见 [.opencode/skills.md](.opencode/skills.md)）。

其它子命令：`agent sbatch`、`agent salloc`（导出环境并透传）、
`agent supervisor`、`agent report --run-dir DIR`、
`agent deploy --mpi-monitor DIR`（同步到 `/shared`）。

默认注入是 overlap step（每节点 1 个 supervisor，`--mem=256M`），用户 `srun`
单独一步以保留 PMI。overlap 在用户命令启动前失败时，回退一次 exec-wrapper。

## 已实现的 skills

两层不要混用。`--agent-skills` 选的是计算节点确定性工具；`.opencode/skills/`
是提交端 OpenCode 解读用的 skill。

### 节点工具（`--agent-skills`）

默认加载全部四个节点工具：
`proc-monitor,mpi-scan,slurm-tap,node-diag`。逗号分隔可覆盖。

| 名称 | 作用 | 产物 |
|------|------|------|
| `proc-monitor` | 按 `--match` 采样用户进程 CPU/RSS/IO（调用 mpi-monitor `collect_loop`） | `series/{host}_pid{pid}.jsonl`；有 matplotlib 时还有 `charts/*.png` |
| `mpi-scan` | 扫 MPI/启动器 stderr 的 abort 模式 | `events/stderr.tail` |
| `slurm-tap` | 解析 scontrol/sstat/sacct 作业状态 | `events/slurm.json` |
| `node-diag` | 计算节点采集本机 OOM / cgroup / hang，`stop` 时再采一次 | `events/node-diag.txt` |

启动器进程（`srun`、`mpirun`、`orted` 等）不会被 `proc-monitor` 采样。

`node-diag` 读 `dmesg` 或 `/dev/kmsg`，以及作业 cgroup 的 `cgroup.procs` 与
`memory.events`（v1 为 `memory.oom_control`）。只把作业范围内的 OOM（cgroup
PID 交集或 `oom_kill` 增量）或纯 hang 快照打成 `node_local`。历史 dmesg 里
其它作业的 `Killed process` 会忽略。读失败写 `events/node_diag.err`，不改
用户退出码。

### OpenCode skills（`.opencode/skills/`）

job-assist 在登录节点加载，用来解读工具产物，不在计算节点跑模型。完整索引见
[.opencode/skills.md](.opencode/skills.md)。

| Skill | 何时用 |
|-------|--------|
| [mpi-monitor](.opencode/skills/mpi-monitor/SKILL.md) | 解读 `series/` 的 CPU/RSS/IO 与 `charts/` 路径；空 series 时区分采集失败与作业未启动 |
| [launch-fail](.opencode/skills/launch-fail/SKILL.md) | `reason_code=execution_error` 且 `pid_count=0`（ENOENT / 二进制不在 NFS） |
| [node-diag](.opencode/skills/node-diag/SKILL.md) | `reason_code=node_local` 或 `events/node-diag.txt` 出现作业内 OOM / cgroup `oom_kill` / NFS hang |

## 测试集群

联调用四台节点：`mn`、`cn1`、`cn2`、`cn3`。单元测试不依赖集群。

当前演示树（从 `mn` 发起；本集群用 NFS `/shared`，不必再 tar 到 cn）：

| 用途 | 路径 |
|------|------|
| 源码 / MPI 二进制 | `/shared/agent-sidecar` |
| mpi-monitor（proc-monitor import） | `/shared/mpi-monitor/src` |
| 部署脚本 | `/shared/agent-sidecar/scripts/deploy_shared.sh` |
| job-assist 演示 | `/shared/agent-sidecar/scripts/demo_job_assist_mpi.sh` |
| MPI IO scratch | `/shared/mpi-io` |
| 运行产物 | `/shared/agent-runs` |

在 **mn** 上：

```bash
ssh mn
bash /shared/agent-sidecar/scripts/deploy_shared.sh /path/to/mpi-monitor
export PYTHONPATH=/shared/agent-sidecar/src PYTHONUNBUFFERED=1 AGENT_VERBOSE=1
bash /shared/agent-sidecar/scripts/demo_job_assist_mpi.sh \
  /shared/agent-sidecar /shared/agent-runs
```

已在分配内时，只跑 wrap：

```bash
export PYTHONPATH=/shared/agent-sidecar/src PYTHONUNBUFFERED=1 AGENT_VERBOSE=1
salloc -N3 -n3 -w cn1,cn2,cn3 -p test
python3 -m agent_sidecar srun --agent-verbose --agent-profile=tools-only \
  --agent-skills=proc-monitor,node-diag \
  --agent-output-dir /shared/agent-runs \
  -n3 -l -- hostname
```

看最新 run 目录下的 `meta.json`、`telemetry.json`。默认 `job-assist` 会在 mn
上跑 OpenCode；上面的 `tools-only` 只采工具。`proc-monitor` 依赖已部署的
mpi-monitor；未部署时 `events/mpi_monitor_import.err`，`series/` 为空。

## 测试

```bash
python3 -m unittest discover -s tests
```
