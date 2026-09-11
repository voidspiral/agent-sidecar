## Why

操作员仍把 sidecar 开关（`--agent-verbose`、`--agent-match`）夹进 `srun`
参数，并在用户二进制前多写一个 `--`。HPC 用户需要 SLURM 那段看起来就是
原生 `srun`，sidecar 选项归 `sidecar.sh` / `sidecar-analy.sh` 所有。

## What Changes

- 首选 wrap 语法：`sidecar.sh [--agent-*] srun <原生 slurm> <用户命令>`。
  `python3 -m agent_sidecar` 同样接受前导 `--agent-*`。
- SLURM 选项与绝对路径用户二进制之间的单独 `--` **不是必须的**。操作员
  若仍写 `--`，原样转给 SLURM。
- 用户二进制 basename 已能匹配时省略 `--agent-match`（proc-monitor 默认）。
  覆盖仍可作为 `sidecar.sh` 选项写在 `srun` **之前**。
- `sidecar-analy.sh --log DIR --code PATH` 不变（选项本来就在脚本上）。
- **非 BREAKING：** 启动器后面的 `srun --agent-* <slurm>` 仍接受，现有
  单测不必一次改光。对外文档和 `测试.md` 只用前置写法。

## Capabilities

### New Capabilities

- （无）

### Modified Capabilities

- `agent-launch`：wrap argv 接受 `srun`/`sbatch`/`salloc` 之前的前导
  `--agent-*`；用户命令不是选项形态时 `--` 可选；公开操作命令把 sidecar
  旗标写在包装脚本上。

## Impact

解析器、脚本注释、`测试.md`、README/demo/pack/deploy、单测。

## Non-goals

ClusterHelm 控制面、未包装的原生 `srun`（SPANK）、把 `--agent-verbose`
改名为 `--verbose`、在 bash 里再维护一套 getopts、改 analy 旗标名、
编造 `reason_code`、计算节点 LLM。
