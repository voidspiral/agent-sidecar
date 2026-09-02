## 背景

动机见 `proposal.md`。一期已有 `agent srun`、overlap supervisor、节点工具、
分类器，以及只记录 `exit_code` 的 wrap 期 `telemetry.json`。
`--agent-profile=job-assist` 能解析但被忽略。`--agent-node-llm` 打印不支持。
登录节点（`mn`）已通过 `AGENT_LLM_*` 暴露 DeepSeek（OpenAI 兼容）。

约束：Python 3.10+；标准库优先；TDD（`unittest`，先写失败测试再实现）；
单元测试不访问网络；禁止硬编码家目录；sidecar 跟随作业生命周期；LLM 不得
作为 `/proc` 主采集器；密钥留在提交端。

## 目标 / 非目标

**目标：**

- 在 wrap 结束、任何模型调用之前，把 series 与工具产物汇总成完整
  `JobTelemetry`。
- 当 `--agent-profile=job-assist` 且凭据存在时，在提交端发起一次
  OpenAI 兼容 chat completion。
- 写出 `JobAssistNote`，不改 `reason_code`，不改用户退出码。

**非目标：**

- 每节点模型运行时、SPANK、自动 `scancel`/`scontrol`、ClusterHelm 适配、
  以 Cursor CLI/SDK 作为 assist 运行时、第三方 HTTP SDK。

## 决策

### 1. 实现方法：TDD

先写失败的 `unittest`：假 chat 客户端（无 socket）、argv/profile 门控、
prompt 内容、`reason_code` 保持、HTTP/超时 fail-soft、wrap 期 summary 字段。
再实现直到测试通过。真实 DeepSeek 探测可选且需门禁（`AGENT_LLM_LIVE=1`），
不算单元测试。

**备选：** 单元测试打真实 API（否决：不稳定、泄密、违反“单测不联网”）。

### 2. Assist 在 wrap 之后跑在提交端，不进 overlap

```
overlap supervisors（仅工具，每节点一个）
        │
   用户 srun（PMI）
        │
   停 sidecar / 回传产物
        │
   写 JobTelemetry（summary + anomalies + reason_code）
        │
   若 profile == job-assist：本机一次 chat
        │
   写 assist/job.json，补 telemetry.job_assist
```

计算节点从不收到 `AGENT_LLM_API_KEY`，也不向供应商发 HTTP。
`--agent-node-llm` 仍为解析后拒绝。

**备选：** overlap 节点 LLM（否决：cn 常无出网、256MiB 预算、密钥扩散）；
Cursor CLI（否决：不是作业生命周期 sidecar）。

### 3. 标准库 OpenAI 兼容客户端

`POST {base}/chat/completions`，`Authorization: Bearer`，JSON
`{model, messages, temperature: 0}`。默认超时 30s（`AGENT_LLM_TIMEOUT`）。
不依赖 `openai` 包。测试注入可调用对象。

API key 只来自环境（绝不用 CLI flag，避免出现在 `ps` / SLURM comment）。
base URL 与 model 来自环境，可用 `--agent-llm-base-url` /
`--agent-llm-model` 覆盖。空 key → 不发 HTTP，collect error
`llm_unconfigured`。

**备选：** Anthropic Messages API（本切片否决：DeepSeek 已在 `/v1` 可用；
mn 上 Anthropic 变量留给其他工具）。

### 4. wrap 期聚合读产物，不读进程内 plugin.events()

远端 supervisor 不会把 `events()` 返回给 CLI。stop 之后，提交端：

- `summarize_series(run_dir)` → 数值 `summary`（空则为 null）
- 扫描 `events/`（MPI stderr tail、`slurm.json`、node-diag 文本）走现有
  分类器 → `anomalies`
- 汇总 `reason_code`：若有工具码则取第一条，否则按用户退出码
  `ok` / `execution_error`

然后才允许 job-assist。Prompt JSON 为
`{summary, anomalies, reason_code, evidence_paths}`，不得包含 series 文件正文。

**备选：** 节点上序列化 plugin events（可后做；产物已能分类则不必）。

### 5. JobAssistNote 模式与 telemetry 回写

写 `assist/job.json`：

```
host: submit
summary: 模型文本
suspected_reason: 拷贝工具 reason_code
evidence_paths: [...]
confidence: 可选
actions: []
```

即使模型建议 `scancel` 也将 `actions` 强制为 `[]`。回写 `telemetry.json`
增加 `job_assist` 与 note 路径；不改 `reason_code`。

### 6. Fail-soft 与退出码

用户命令退出码原样返回。Assist 错误（`llm_unconfigured`、`llm_http`、
`llm_timeout`、`llm_parse`）进入 `collect_errors`。超时用
`urlopen(..., timeout=)`。

## 风险 / 权衡

- [密钥落到计算节点] → 绝不把 `AGENT_LLM_*` 导出进 sidecar `srun`。
- [Prompt 泄漏 JSONL] → 单测请求体；只传合同 dict。
- [模型编造原因] → `reason_code` 从 telemetry 拷贝，从不从模型 JSON 取值。
- [供应商宕/慢] → 30s 超时、fail-soft、保留用户退出码。
- [产物不全] → 空 series 用 null summary；profile 与凭据仍在则仍调用模型。
- [ps 泄漏] → API key 仅环境变量。

## 迁移计划

- 现有 `tools-only` wrap 会得到更完整的 `summary`/`anomalies`，无 LLM。
- `job-assist` 为 opt-in。未设 key → collect error，用户退出码不变。
- 回滚：去掉 `--agent-profile=job-assist` 或 unset `AGENT_LLM_API_KEY`。
- 不交付节点 LLM 或 `scancel` stub。

## 待决问题

- 默认模型名保持主机上的 `AGENT_LLM_MODEL`（mn 上现为 `deepseek-v4-flash`），
  不写进源码。
- `agent report` 是否美化打印 `job_assist` 可后做；本切片 JSON dump 即可。
