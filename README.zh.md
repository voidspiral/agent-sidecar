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
| `--agent-llm-base-url` | 覆盖 `AGENT_LLM_BASE_URL`（job-assist） |
| `--agent-llm-model` | 覆盖 `AGENT_LLM_MODEL`（job-assist） |

`job-assist` 在提交端、写出 `telemetry.json` 之后调用一次 OpenAI 兼容接口，
不在计算节点上跑模型。凭据只用环境变量（API key 禁止作为 CLI flag）：

```bash
export AGENT_LLM_BASE_URL=https://api.example.com/v1
export AGENT_LLM_API_KEY=...   # 不要提交进仓库
export AGENT_LLM_MODEL=your-model

python3 -m agent_sidecar srun --agent-profile=job-assist \
  --agent-skills=proc-monitor,slurm-tap,mpi-scan,node-diag \
  --agent-output-dir /tmp/agent-runs \
  -N 2 -n 4 -- ./app
```

缺凭据或供应商错误写入 `collect_errors`，不替换用户退出码，也不改
`reason_code`。

约 60 秒、带 IO 的 MPI 示例见 `examples/mpi_io_load.c`。在登录节点：

```bash
bash scripts/demo_job_assist_mpi.sh
```

其它子命令：`agent sbatch`、`agent salloc`（导出环境并透传）、
`agent supervisor`、`agent report --run-dir DIR`。

默认注入是 overlap step（每节点 1 个 supervisor，`--mem=256M`），用户 `srun`
单独一步以保留 PMI。overlap 在用户命令启动前失败时，回退一次 exec-wrapper。

## 测试集群

联调用四台节点：`mn`、`cn1`、`cn2`、`cn3`。单元测试不依赖集群。

当前演示树（从 `mn` 发起，无共享文件系统时需把 `src` 同步到计算节点）：

| 用途 | 路径 |
|------|------|
| 源码 | `/tmp/agent-sidecar` |
| 演示脚本 | `/tmp/agent-sidecar/scripts/demo_three_nodes.sh` |
| 运行产物 | `/tmp/agent-runs` |

在 **mn** 上：

```bash
ssh mn
export PYTHONPATH=/tmp/agent-sidecar/src PYTHONUNBUFFERED=1 AGENT_VERBOSE=1
bash /tmp/agent-sidecar/scripts/demo_three_nodes.sh /tmp/agent-sidecar /tmp/agent-runs
```

已在分配内时，只跑 wrap：

```bash
export PYTHONPATH=/tmp/agent-sidecar/src PYTHONUNBUFFERED=1 AGENT_VERBOSE=1
salloc -N3 -n3 -w cn1,cn2,cn3 -p test
python3 -m agent_sidecar srun --agent-verbose --agent-profile=tools-only \
  --agent-skills=proc-monitor,node-diag \
  --agent-output-dir /tmp/agent-runs \
  -n3 -l -- hostname
```

看最新 run 目录下的 `meta.json`、`telemetry.json`。一期 `tools-only` 会把
supervisor 打到各节点；`proc-monitor` / `node-diag` 的真实采集仍依赖注入的
采集函数，空跑时 `series/` 可能为空。

## 测试

```bash
python3 -m unittest discover -s tests
```
