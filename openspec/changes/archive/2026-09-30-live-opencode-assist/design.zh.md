## 背景

动机见 proposal.md。当前 wrap（`run.py`）先起 overlap supervisor，阻塞在用户
`srun` 上，再写 `telemetry.json`；仅当 `profile == "job-assist"` 时调用一次
`run_opencode_assist`（`opencode run --auto`，stdin 为 `DEVNULL`）。
`AgentOptions.profile` 默认 `tools-only`。节点工具已在作业寿命内采样。
OpenCode 必须留在提交端；测试注入 runner，不执行真实 `opencode`。

实现方法：TDD（先失败的 unittest，再写代码）。

## 目标 / 非目标

**目标：**

- 默认 `agent srun` 即 job-assist（工具 + 提交端 OpenCode）。
- 用户 step 期间在提交端跑 live watcher，对制品快照做 tick；wrap 写出
  telemetry 后再出一份最终笔记。
- 无 TTY 时不阻塞在对话提示上；有 TTY 的对话不得占用用户 PMI `srun` 的 stdin。
- 缺少 OpenCode 时 fail-soft。

**非目标：**

- 设计层：不新增计算节点 OpenCode 协议；不强制 tmux；不 HTTP 回退；不改
  overlap 注入或 mpi-monitor collect。

## 决策

1. **默认 profile 为 `job-assist`。** 用 `agent` 包装即要 assist。
   `tools-only` 为显式关闭。备选：保持 tools-only 默认再加配置文件——本变更
   拒绝，因为需求是「默认启动 OpenCode」；配置覆盖可留到后续。

2. **Live 路径是 wrap 拥有的提交端 watcher，不是第二次 `srun`。** 在 run 目录
   就绪且 overlap（或 fallback）拉起之后、`run_user` 之前 start；与节点
   sidecar 同一有界 join 里 stop。备选：在计算节点 `srun --overlap` OpenCode
   ——拒绝（无出网、密钥、易去刮 `/proc`）。

3. **分析始终用 `--auto` tick；交互是 attach + stderr，不是 PMI stdin。**
   后台 ticker 定期对当前 `series/` 做 `summarize_series` 并加上 `events/`，
   注入 runner 带 `--auto`。默认间隔 `15s`，环境变量
   `AGENT_OPENCODE_LIVE_INTERVAL`（flag 可后补）。wrap 的 stdin/stdout 是 TTY
   时，向 stderr 打一行 attach 提示，并可回显 tick 摘要；不把 OpenCode 接到
   用户 `srun` 的 stdin。无 TTY：只 tick，无提示、不读 stdin。备选：前台
   OpenCode、后台用户 step——拒绝（破坏 PMI 和批脚本）。备选：tmux 分屏——拒绝。

4. **最终笔记合同不变。** sidecar 停后写 telemetry 和 charts，再调用一次
   `run_opencode_assist`。`assist/` 下 live 文件不得覆盖 `reason_code`。

5. **测试注入 `LiveWatcher`：** `start(run_dir)`、`tick()`、`stop()`。默认实现
   调 `opencode`；单测不碰 PATH。

6. **演示保持无 TTY `--auto`。** 默认翻转后 `demo_job_assist_mpi.sh` 可去掉
   `--agent-profile=job-assist`；不得要求 TTY。README 最短命令为
   `agent srun -N3 -n3 -p test -- ./app`。

## 风险 / 权衡

- [15s tick 触发 OpenCode 费用/限流] → 间隔可配；快照 hash 不变则跳过 tick；
  超时 fail-soft。
- [NFS 延迟导致前几拍 series 为空] → 空快照合法；不编造 `reason_code`。
- [用户以为能在同一终端和 `srun` 聊天] → stderr 提示 + attach；文档写第二
  终端；不抢 PMI stdin。
- [默认 job-assist 让没装 OpenCode 的主机“坏掉”] → 已规定 `opencode_missing`；
  工具和用户退出码不变。
- [单测假设省略 profile 即 tools-only] → 先改这些测试（TDD）。

## 迁移

- 在 `argv.py` 翻转默认；先改 profile 单测；再 watcher；再接入 wrap；最后
  README / `AGENTS.md` / `openspec/config.yaml` 里默认 placement 那一行。
- 回滚：`--agent-profile=tools-only` 或还原默认。

## 未决问题

- OpenCode attach 的具体 CLI（`opencode attach` 还是打印 session id）可在
  apply 时选定，不改变「第二终端 / 不抢 PMI」这条规则。
