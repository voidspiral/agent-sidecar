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
agent srun --agent-profile=tools-only \
  --agent-skills=proc-monitor,slurm-tap,mpi-scan,node-diag \
  --agent-output-dir ./runs \
  -N 2 -n 4 -- ./app
```

默认 `--agent-profile` 为 `tools-only`（确定性节点工具，无 LLM）。

| 参数 | 含义 |
|------|------|
| `--agent-profile` | `tools-only`（默认）、`node-assist`、`job-assist` |
| `--agent-skills` | 节点 sidecar 加载的工具，逗号分隔 |
| `--agent-output-dir` | run 目录的父路径（或设 `AGENT_JOB_DIR`） |
| `--agent-verbose` | 打印 overlap sidecar / 用户 step 的启动过程 |
| `--agent-node-llm` | 可选节点模型；记录为不支持 |
| `--agent-match` | 覆盖 proc-monitor 的 `--match`（默认用用户二进制基名） |
| `--agent-interval` | 采样间隔秒（默认 `1.0`） |

`job-assist` 在提交端、写出 `telemetry.json` 之后调用一次 OpenCode
（`opencode run --dir <本仓库>`），不再 `POST /chat/completions`，不 source
任何供应商 env 文件，也不在计算节点上跑模型。OpenCode 用登录节点上自己的
配置。进程环境里若已有供应商变量，会从 sidecar `srun` 剥掉。缺少 `opencode`
时 **不会** 回退 HTTP。

```bash
# 在 mn 上；凭据留在 OpenCode 自己的配置里，不要拷到计算节点或 git

python3 -m agent_sidecar srun --agent-profile=job-assist \
  --agent-skills=proc-monitor,slurm-tap,mpi-scan,node-diag \
  --agent-output-dir /tmp/agent-runs \
  -N 2 -n 4 -- ./app
```

缺少 OpenCode 或 runner 失败写入 `collect_errors`（`opencode_missing` /
`opencode_timeout` / `opencode_failed`），不替换用户退出码，也不改
`reason_code`。

mpi-monitor 源码默认 `/shared/mpi-monitor/src`，可用 `AGENT_MPI_MONITOR_SRC`
覆盖。有 matplotlib 时 wrap 会在 `charts/` 写出 PNG。

可选：设 `AGENT_OPENCODE_MODEL`（`provider/model`）固定模型。

约 60 秒、带 IO 的 MPI 示例见 `examples/mpi_io_load.c`。本集群 NFS 挂在
`/shared`（`mn:/shared`）。源码、二进制、IO scratch 和 run 产物都放这里，
各节点同一份文件：

```bash
# 在 mn 上
rsync -az ./ /shared/agent-sidecar/
rsync -az /path/to/mpi-monitor/ /shared/mpi-monitor/
bash /shared/agent-sidecar/scripts/demo_job_assist_mpi.sh \
  /shared/agent-sidecar /shared/agent-runs
```

启动失败（故意缺失二进制）给 OpenCode 诊断：

```bash
bash /shared/agent-sidecar/scripts/demo_opencode_launch_fail.sh
```

作业把每 rank 文件写到 `/shared/mpi-io`（可用 `AGENT_MPI_WORKDIR` 覆盖）。
OpenCode 凭据留在登录节点 OpenCode 自己的配置里，不上 NFS、不进本仓库。

OpenCode 常驻说明：`AGENTS.md`（与 `agent.md` 同文）。Skills：
`.opencode/skills/`。

其它子命令：`agent sbatch`、`agent salloc`（导出环境并透传）、
`agent supervisor`、`agent report --run-dir DIR`。

默认注入是 overlap step（每节点 1 个 supervisor，`--mem=256M`），用户 `srun`
单独一步以保留 PMI。overlap 在用户命令启动前失败时，回退一次 exec-wrapper。

## 测试集群

联调用四台节点：`mn`、`cn1`、`cn2`、`cn3`。单元测试不依赖集群。

当前演示树（从 `mn` 发起；本集群用 NFS `/shared`，不必再 tar 到 cn）：

| 用途 | 路径 |
|------|------|
| 源码 / MPI 二进制 | `/shared/agent-sidecar` |
| job-assist 演示 | `/shared/agent-sidecar/scripts/demo_job_assist_mpi.sh` |
| MPI IO scratch | `/shared/mpi-io` |
| 运行产物 | `/shared/agent-runs` |

在 **mn** 上：

```bash
ssh mn
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

看最新 run 目录下的 `meta.json`、`telemetry.json`。一期 `tools-only` 会把
supervisor 打到各节点；`proc-monitor` / `node-diag` 的真实采集仍依赖注入的
采集函数，空跑时 `series/` 可能为空。

## 测试

```bash
python3 -m unittest discover -s tests
```
