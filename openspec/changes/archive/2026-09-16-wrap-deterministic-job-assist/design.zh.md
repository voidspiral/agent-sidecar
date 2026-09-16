## 背景

`run_job_assist` 目前会 unlink pack 已写的 `assist/job.json`，并在 wrap 后
总是 spawn `opencode run`（除非 `AGENT_OPENCODE_FINAL_TIMEOUT=0`）。健康作业
没有 live 笔记，因此每次成功的 MPI wrap 都要付一整轮 OpenCode。pack 笔记
即使已有中文建议也会被丢掉。

## 目标 / 非目标

**目标：**

- 健康作业（`reason_code=ok`、无 anomalies）仍得到 `assist/job.json`，分条
  简体中文：结论、采集指标、异常（无）、以及根据 CPU/RSS/IO/以太网 / pid
  数得出的 **建议**。
- 默认 wrap 墙钟不等待 OpenCode。
- pack 写过的笔记在 wrap 后保留。
- TDD（先写失败 unittest）。

**非目标：**

- ClusterHelm 控制面。
- 改 live 异常 OpenCode 或 `agent analy --llm`。
- 推断未采集的 Lustre OST 计数。

## 决策

1. **wrap 默认走确定性路径。** `AGENT_OPENCODE_FINAL_TIMEOUT` 未设置或为 `0`
   （或 `timeout<=0`）时跳过 OpenCode，写或保留笔记。**正数**
   `AGENT_OPENCODE_FINAL_TIMEOUT` 恢复今天的 unlink + `run_opencode_assist`
   逃逸口。
2. **健康作业建议是一等模块**（`resource_hints.chinese_summary`），不是空
   stub。启发式只读 `JobTelemetry` 的 `summary` / `anomalies` /
   `reason_code`（不读 JSONL 正文）。始终输出 `4. 建议：…`。规则：未匹配
   pid；低/高 `cpu_peak`；IO 相对 CPU；以太网峰值是主机 NIC 不是 MPI 字节；
   若无规则命中，仍建议保持当前 `srun`/`--interval`。
3. **优先级：** live.json 摘要 → 提升；否则已有 job.json 摘要（pack）→ 保留
   并列入 telemetry；否则 resource hints。
4. **`agent analy --llm` 不变：** 仍可 unlink 并 spawn OpenCode。

## 风险 / 权衡

- 启发式建议比模型浅。接受：需要速度和基于监控的建议；`analy --llm` 仍在。
- wrap 已写的 stub pack 文案不由 hints 重写。本变更接受。
- 以前 `timeout=0` 不写 `job.json`；现在写 hints，健康作业仍有建议。

## 迁移

无磁盘 schema 变更。依赖 wrap OpenCode 的操作员把
`AGENT_OPENCODE_FINAL_TIMEOUT` 设为正数预算。

## 未决问题

无。
