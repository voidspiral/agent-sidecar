# 用例库（目录名 = 调研2 总表 ID）

登录节点 `mn`。`make -C examples` 递归全部总表目录，并编译根目录健康对照
`mpi_io_load.c`。硬件 `18`–`23` 的 `all` 仍为空目标。`2a` 与 `2b` 合成 `02/`
（2a 仅单测注入，禁止 srun 撑节点）。

两条入口与仓库根 `测试.md` 相同：

- `sidecar.sh [--agent-*] srun <原生 slurm> <用户命令>`
- `sidecar-analy.sh --log DIR --code SRC`

sidecar 开关写在 `srun` **之前**。`--agent-match` 是 sidecar 选项，写在 `srun` 前；
省略时默认用用户二进制 basename。绝对路径不必 `--`。
`--agent-profile=tools-only` 才关闭伴随启动的模型。
不要设 `AGENT_OPENCODE_FINAL_TIMEOUT=0`（会跳过 wrap 期末轮模型）。

脚本自己设 `PYTHONPATH`。查 run 目录用 `sidecar.sh report`。

```shell
unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
CC=mpicc make -C /shared/agent-sidecar/examples
```

Live plot 默认 `http://127.0.0.1:8765`。笔记本：`ssh -L 8765:127.0.0.1:8765 mn`。
集群网卡直连：[agent live plot](http://192.168.182.136:8765/)

作业结束后（每个用例都适用）：

```shell
RUN=$(ls -1dt /shared/agent-runs/20* | head -1)
echo "RUN=$RUN"
bash /shared/agent-sidecar/scripts/sidecar.sh report --run-dir "$RUN"
cat "$RUN/assist/job.json"
```

`--log` 就是这个 `$RUN`，不是 SLURM `.out`。批量断言（可选，会设
`AGENT_OPENCODE_FINAL_TIMEOUT=0`）：`bash /shared/agent-sidecar/scripts/run_fault_case.sh <id>`。

本集群：`salloc -N2 -n2 -w cn[1-2] -p test`。accounting 往往未开，`--mem` 可能不强制
cgroup；见 02 / 12。

| 目录 | 总表 ID | 内容 | 是否完成 | 期望主码 |
| --- | --- | --- | --- | --- |
| （根） | — | `mpi_io_load.c` 健康对照 | 对照 | `ok` |
| `01/` | 1 | 缺动态库 | **完成** | `execution_error` / `launch_fail` |
| `02/` | 2a + 2b | 内核 OOM / cgroup OOM | 2b 夹具；2a 仅单测 | 2b `slurm_oom`；2a `node_local` |
| `03/` | 3 | 段错误 | **完成** | `mpi_segfault` |
| `04/` | 4 | CRLF | **完成** | `execution_error` / `launch_fail` |
| `05/` | 5 | SIGFPE | **完成** | `mpi_fpe` |
| `06/` | 6 | MPI 死锁 | **完成** | `mpi_deadlock` |
| `06x/` | 6x | MPI_Abort | **完成** | `mpi_abort` |
| `07a/` | 7a | 应用 I/O 失败 | **完成** | `execution_error` |
| `07b/` | 7b | I/O 空转 | 未完成 | — |
| `08/` | 8 | 数值发散 exit 0 | 未完成 | — |
| `09/` | 9 | OpenMP 超订 | 未完成 | — |
| `10/` | 10 | 启动失败 | **完成** | `execution_error` + `pid_count=0` |
| `11a/` | 11a | 非法 srun 参数 | **完成** | `execution_error` |
| `11b/` | 11b | 超订变慢 | 未完成 | — |
| `12/` | 12 | TimeLimit | **完成** | `timeout` |
| `13/` | 13 | cgroup 内存超限 | **完成**（复用 02） | `slurm_oom` |
| `14/` | 14 | Pending | 未完成 | — |
| `15/` | 15 | Prolog/Epilog | 仅单测 | `node_fail` |
| `16/` | 16 | 环境未 inherit | **完成** | 同 01 |
| `17/` | 17 | drain/down | 未完成 | — |
| `18/`–`23/` | 18–23 | 硬件 | 空目标 | — |

---

# 正常用例（`mpi_io_load`）

伴随 `srun` 启动 sidecar。健康作业没有 live 异常触发，作业结束后应由期末 OpenCode
写出 `assist/job.json`。`--agent-match=mpi_io_load`。

```shell
unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh --agent-match=mpi_io_load srun -n2 \
    /shared/agent-sidecar/examples/mpi_io_load 15 /shared/mpi-io 0
```

看 live plot 可用更长 IO（60s）：

```shell
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh --agent-verbose --agent-match=mpi_io_load srun -n2 \
    /shared/agent-sidecar/examples/mpi_io_load 60 /shared/mpi-io
```

```shell
RUN=$(ls -1dt /shared/agent-runs/20* | head -1)
bash /shared/agent-sidecar/scripts/sidecar.sh report --run-dir "$RUN"
cat "$RUN/assist/job.json"
```

期望：`reason_code=ok`，`pid_count>0`，`series/` 有 JSONL；report 中有「1. 结论：…」；
正常作业不需要 `--code`。

---

# 01 缺动态库

`-Wl,-rpath` 指向不部署的 `libmissing.so`。`--agent-match=mpi_missing_so`。

```shell
CC=mpicc make -C /shared/agent-sidecar/examples/01

unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh --agent-match=mpi_missing_so srun -n1 \
    /shared/agent-sidecar/examples/01/mpi_missing_so
```

期望：`reason_code=execution_error`，`pid_count=0`，pack=`launch_fail`；
stderr 含 `cannot open shared object file`。

---

# 02 / 2b cgroup malloc（Slurm OOM）

`cgroup_oom` 默认 malloc 256MiB。2a 内核 OOM **不要**用本二进制撑节点。

```shell
CC=mpicc make -C /shared/agent-sidecar/examples/02

unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N1 -n1 -w cn1 -p test --mem=16M \
  bash /shared/agent-sidecar/scripts/sidecar.sh --agent-match=cgroup_oom srun -n1 --mem=16M \
    /shared/agent-sidecar/examples/02/cgroup_oom
```

期望（站点强制 cgroup 时）：`reason_code=slurm_oom`，pack=`stub`，`pid_count>0`。
本集群若 accounting 关闭、`--mem` 不杀进程，会 `ok` 且 rss≈256MB；不要为了出码去打满节点。

---

# 2a 内核 OOM Killer

**不要 srun。** 会打节点。分类仅 unittest 注入 `Killed process` → `node_local`。

---

# 03 段错误

`10 0` = 工作 10 秒后 rank 0 空指针。`--agent-match=mpi_fault_segfault`。

```shell
CC=mpicc make -C /shared/agent-sidecar/examples/03

unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh --agent-match=mpi_fault_segfault srun -n2 \
    /shared/agent-sidecar/examples/03/mpi_fault_segfault 10 0
```

```shell
RUN=$(ls -1dt /shared/agent-runs/20* | head -1)
bash /shared/agent-sidecar/scripts/sidecar.sh report --run-dir "$RUN"
bash /shared/agent-sidecar/scripts/sidecar-analy.sh \
  --log "$RUN" --code /shared/agent-sidecar/examples
cat "$RUN/assist/analysis.json"
cat "$RUN/assist/job.json"
```

期望：`reason_code=mpi_segfault`，`pid_count>0`；stderr 含 `rank 0 segfault`；
不要编造未授权 `file:line`。

## 03 NPB CG 中途段错误

NAS NPB 3.4-MPI **CG Class B**，两 rank。补丁在 `examples/03/npb_cg_mid_segfault/`。
原树 `/shared/NPB3.4.3` 不改。`srun` 必须 `--mpi=pmi2`。`--agent-match=cg.B.x`。

不要在 WSL 上当集群跑。

```shell
export NPB_MPI_ROOT=/shared/NPB3.4.3/NPB3.4-MPI
export AGENT_SHARED=/shared
bash /shared/agent-sidecar/examples/03/npb_cg_mid_segfault/build.sh

unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh \
    --agent-verbose \
    --agent-skills=proc-monitor,slurm-tap,mpi-scan,node-diag,eth-monitor \
    --agent-match=cg.B.x \
    srun --mpi=pmi2 -n2 \
    /shared/agent-sidecar/examples/03/cg.B.x
```

`--code` 必须指向打过补丁的 Fortran 树，不要指干净的 `/shared/NPB3.4.3`：

```shell
RUN=$(ls -1dt /shared/agent-runs/20* | head -1)
bash /shared/agent-sidecar/scripts/sidecar-analy.sh \
  --log "$RUN" --code /shared/npb-build/cg-mid-segfault
```

期望：stderr 含 `rank 0 segfault (null deref)`；`reason_code=mpi_segfault`。

---

# 04 CRLF `job.sh`

必须 **exec** 该脚本（不要 `bash job.sh`，否则忽略 shebang 里的 `^M`）。

```shell
make -C /shared/agent-sidecar/examples/04
chmod +x /shared/agent-sidecar/examples/04/job.sh

unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh srun -n1 \
    /shared/agent-sidecar/examples/04/job.sh
```

期望：`execution_error` / `launch_fail`；stderr 含 `bad interpreter`。

---

# 05 SIGFPE（`mpi_fpe`）

忙等后 `raise(SIGFPE)`，先打印 `rank N fpe`。pack 为 `stub`。

```shell
CC=mpicc make -C /shared/agent-sidecar/examples/05

unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh --agent-match=mpi_fault_fpe srun -n2 \
    /shared/agent-sidecar/examples/05/mpi_fault_fpe 10 0
```

期望：`reason_code=mpi_fpe`（rollup 优先于 `slurm_failed`）。

---

# 06 MPI 死锁（`mpi_deadlock`）

打印 `rank N deadlock` 后 rank0 跳过 `MPI_Barrier`。**必须带 `--time`**。

```shell
CC=mpicc make -C /shared/agent-sidecar/examples/06

unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh --agent-match=mpi_fault_deadlock srun -n2 --time=00:00:10 \
    /shared/agent-sidecar/examples/06/mpi_fault_deadlock 5 0
```

期望：主码 **`mpi_deadlock`**（优先于 `timeout` / `slurm_failed`）。

---

# 06x MPI_Abort

`10 0 1` = 工作 10 秒后 rank 0 `MPI_Abort(..., 1)`。`--agent-match=mpi_fault_abort`。

```shell
CC=mpicc make -C /shared/agent-sidecar/examples/06x

unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh --agent-match=mpi_fault_abort srun -n2 \
    /shared/agent-sidecar/examples/06x/mpi_fault_abort 10 0 1
```

```shell
RUN=$(ls -1dt /shared/agent-runs/20* | head -1)
bash /shared/agent-sidecar/scripts/sidecar.sh report --run-dir "$RUN"
bash /shared/agent-sidecar/scripts/sidecar-analy.sh \
  --log "$RUN" --code /shared/agent-sidecar/examples
cat "$RUN/assist/analysis.json"
cat "$RUN/assist/job.json"
```

只要 pack、不调模型时加 `--no-llm`。期望：`reason_code=mpi_abort`，`pid_count>0`。

---

# 07a 应用 I/O 失败（ENOENT）

```shell
CC=mpicc make -C /shared/agent-sidecar/examples/07a

unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh --agent-match=io_enoent srun -n1 \
    /shared/agent-sidecar/examples/07a/io_enoent
```

期望：`execution_error`；stderr `No such file or directory`。退出太快时
`pid_count=0`，pack 可能是 `launch_fail`。

---

# 07b I/O 空转

**未实现。** 原因：`io_stall` 时段检测未做，Makefile `all` 为空。不要当必跑用例。

---

# 08 数值发散但退出 0

**未实现。** 原因：残差 NaN / 科学对错不是 sidecar 故障码，exit 0 会标 `ok`。

---

# 09 OpenMP 超订变慢

**未实现。** 原因：`OMP_NUM_THREADS` 过大只变慢，不产生 tool anomaly。

---

# 10 可执行文件不存在

路径必须不存在：`examples/10/no-such-mpi`。不要创建该文件。

```shell
unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh srun -n1 \
    /shared/agent-sidecar/examples/10/no-such-mpi
```

期望：`execution_error`，`pid_count=0`，pack=`launch_fail`。

---

# 11a 非法 srun 分区

**不要**把 `-p __no_such_partition__` 写进已有 `salloc -p test`：内层 `-p` 会被分配吃掉。
在登录节点直接：

```shell
unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
bash /shared/agent-sidecar/scripts/sidecar.sh srun -p __no_such_partition__ -n1 hostname
```

期望：`execution_error`；stderr `invalid partition specified`。

---

# 11b 合法但超订变慢

**未实现。** 原因：同 09，合法 `--ntasks` 与核数不匹配只变慢，无失败码。

---

# 12 TimeLimit

```shell
make -C /shared/agent-sidecar/examples/12
chmod +x /shared/agent-sidecar/examples/12/sleep_timeout.sh

unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh srun -n1 --time=00:00:10 \
    /shared/agent-sidecar/examples/12/sleep_timeout.sh
```

期望：`reason_code=timeout`。若 accounting 关闭，stderr 仍可能有 `DUE TO TIME LIMIT`，
但 `slurm.json` 停在 salloc 的 `RUNNING`，主码会落成 `execution_error`。

---

# 13 cgroup 内存超限

复用 `02/cgroup_oom`。跑法同 02：

```shell
CC=mpicc make -C /shared/agent-sidecar/examples/13

unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N1 -n1 -w cn1 -p test --mem=16M \
  bash /shared/agent-sidecar/scripts/sidecar.sh --agent-match=cgroup_oom srun -n1 --mem=16M \
    /shared/agent-sidecar/examples/02/cgroup_oom
```

期望：同 02，`slurm_oom`（受站点 cgroup 限制）。

---

# 14 Pending 过久

**未实现。** 原因：Pending 在用户 `srun` 作业步之前，sidecar 不包调度等待。

---

# 15 Prolog / Epilog → `NODE_FAIL`

**不要 srun。** 禁止打真实节点。仅 unittest 注入 `NODE_FAIL` → `node_fail`。

---

# 16 环境未 inherit

复用 01 缺库二进制 + `srun --export=NONE`。

```shell
CC=mpicc make -C /shared/agent-sidecar/examples/16

unset AGENT_OPENCODE_FINAL_TIMEOUT
export AGENT_LIVE_PLOT_HOST=0.0.0.0
export MPLBACKEND=Agg
salloc -N2 -n2 -w cn[1-2] -p test \
  bash /shared/agent-sidecar/scripts/sidecar.sh srun -n1 --export=NONE \
    /shared/agent-sidecar/examples/01/mpi_missing_so
```

期望：同 01，`execution_error` / `launch_fail`。

---

# 17 节点 drain / down

**未实现。** 原因：禁止 `scontrol drain`。

---

# 18 节点宕机 / MCE

**未实现。** 原因：硬件空目标；真宕机不可作为 demo。

---

# 19 网络 / IB

**未实现。** 原因：无 IB 专用码，禁止打真实网卡。硬件空目标。

---

# 20 Lustre / OST

**未实现。** 原因：禁止打真实 OST；`io_stall` 未做。硬件空目标。

---

# 21 GPU ECC / 掉卡

**未实现。** 原因：无 GPU 采集工具。硬件空目标。

---

# 22 过热降频

**未实现。** 原因：不制造热故障，无温度码。硬件空目标。

---

# 23 电源掉电

**未实现。** 原因：同 18。硬件空目标。
