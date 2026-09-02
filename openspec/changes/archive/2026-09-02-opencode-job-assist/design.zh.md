## 背景

动机见 `proposal.md`。当前 wrap 会直连 DeepSeek HTTP，且 `ProcMonitor` 在没有
`collect_fn` 时直接空返回，所以线上 `series/` 为空。OpenCode 只在登录节点 mn
上跑；DeepSeek 所用模型为纯文本，禁止把 PNG 发给模型。

约束：Python 3.10+；标准库优先；TDD（先失败单测再实现）；单测不访问网络、不
执行真实 `opencode`、不依赖真 `/proc`；密钥留在提交主机。

## 目标 / 非目标

**目标：** overlap 里跑 `collect_loop` 直到 stop；wrap 后本地出 PNG；用一次
可注入的 OpenCode 替换 HTTP job-assist；仓库内改写 skills；启动失败夹具用文本
给出改正命令。

**非目标：** 节点 OpenCode、SPANK、自动 `scancel`/`scontrol`、ClusterHelm 适配、
Cursor CLI/SDK、把图发给 DeepSeek。

## 决策

### 1. 实现方法：TDD

先写失败单测：假 `collect_loop`、假 plotter、假 OpenCode runner、`--match` /
`--agent-match`、缺二进制/超时/失败 fail-soft、wrap 不再走 HTTP。再实现到测试
通过。NFS/OpenCode 真跑属于运维验证，不是单测。

### 2. supervisor 线程里 collect_loop，SIGTERM 写 stop 文件

生产路径：`collect_fn is None` 时 import `mpi_monitor.collect.collect_loop`。
`--match` 取用户 argv0 基名，可用 `--agent-match` 覆盖。supervisor argv 必须带
`--match` 和 `--interval`。

### 3. PYTHONPATH = sidecar src + mpi-monitor src

`AGENT_MPI_MONITOR_SRC` 或 `/shared/mpi-monitor/src`。sidecar 环境去掉
`AGENT_LLM_*` 和 `ANTHROPIC_*`。

### 4. wrap 先 plot 再 OpenCode

`opencode run --dir <repo_root>`，超时默认 120s。Prompt 只带
`summary/anomalies/reason_code/evidence_paths`。禁止 HTTP 回退。

### 5. Fail-soft 错误码

`opencode_missing` / `opencode_timeout` / `opencode_failed` /
`mpi_monitor_import`。不改用户退出码和 `reason_code`。

### 6. OpenCode 文档与 skills

`agent.md` 与 `AGENTS.md` 同文；`skills.md` 索引；mpi-monitor skill 去掉
ClusterHelm 控制面；图只解读路径。

### 7. 启动失败夹具

故意跑不存在的二进制 → `execution_error`；笔记给出改正后的 NFS 路径 / 编译步骤。

## 风险

- match 错导致空 series → 基名 + `--agent-match`
- 节点 import 失败 → collect error，不崩用户作业
- mn 没有 opencode → 记录并停止，禁止 HTTP
- 密钥进计算节点 → sidecar 环境剥离
- 模型编造原因 → 拷贝工具 `reason_code`

## 迁移

`tools-only` 获得采集与图，不调 OpenCode。`job-assist` 依赖提交主机上的
`opencode`。回滚：去掉该 profile。
