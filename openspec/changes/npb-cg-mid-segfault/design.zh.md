## 背景

见 proposal.md（Why）。现有 `mpi_io_load` / `mpi_fault_segfault` 都是短 C 程序。
P4 要用 NAS NPB 3.4-MPI 作为约 60s 集群演示。选定 CG：允许 2 rank，计算加不规则通信；
本集群两节点上默认 Class B（`niter=75`）作为时长目标。在 mn / NFS 上编译运行，不要把 WSL 当集群。

约束：Python 3.10+ unittest TDD；不做 ClusterHelm；不写死用户家目录；不改 `reason_code` 语义。

## 目标 / 非目标

**目标：**

- 把 NPB 3.4-MPI 拷到构建工作目录，对 `CG/cg.f90` 打 unified diff，`make cg CLASS=B`，把二进制装到 `examples/`。
- Rank 0 在 CG 计时区达到 30 秒（约 60s 目标的一半）时打印与 `mpi_fault_segfault` 相同的 stderr 行后崩溃。其它 rank `sleep(3)` 再 `exit(0)`，避免 SLURM 挂起。
- Demo 脚本加上 `--agent-match`，供 proc-monitor / eth-monitor 使用。

**非目标：**

- 把 NAS 源码放进 git。
- 某天墙钟时间不是正好 60s 就改 class。
- 新的 classify/pack 码。

## 决策

1. **实现方法：TDD。** 先写失败的 unittest：把补丁打到 `CG/cg.f90` 副本（CI 若没有 NPB，则打到测试里保存的迭代循环片段），断言中点守卫和 stderr 字符串。再补 build/demo 脚本。约 60s 实跑是集群 demo，不是 CI。

2. **内核 = CG Class B，2 rank。** P4 表把 CG 列为通信算例且 rank 约束较宽。Class A（`niter=15`）在本机往往太短；Class B（`niter=75`，`na=75000`）作为约 60s 目标。可用 `NPB_CG_CLASS` 覆盖。

3. **不内嵌 NPB。** 要求 `NPB_MPI_ROOT`（含 `CG/cg.f90` 和 `Makefile` 的目录）。构建拷到 `$AGENT_SHARED/npb-build/cg-mid-segfault`（默认 `/shared/npb-build/...`），原树保持干净。曾考虑 git submodule，因体积和拷贝噪音放弃。

4. **补丁打在主 inverse-power 循环，而不是包一层二进制。** 在 `conj_grad` 之后、`timer_read(1) >= 30` 秒时注入，保证已发生通信。本集群两 rank 上 Class B 若跑到 `niter/2` 远超 60s；墙钟 30s 对应 P4 约 60s 算例的中途故障。存活 rank 必须像 `mpi_fault_segfault` 一样 `_exit`。

5. **用 `iso_c_binding` 的 `c_null_ptr` 空指针写**，不用 `MPI_Abort` 或 `raise(SIGSEGV)`，与 C 故障件一致。向 unit 0（stderr）打印 `rank 0 segfault (null deref)`，沿用现有 classify/pack。

6. **`--agent-match` 用安装后的 basename**（例如 `cg.B.x`）。Linux `comm` 只有 15 字节；名字变长时靠 argv0 匹配。

## 风险 / 权衡

- [本集群 Class B 墙钟不是 60s] → 文档提供 `NPB_CG_CLASS=A|B`；默认仍为 B。
- [部分编译器 unit 0 不是 stderr] → 使用 `write(0,...)`；demo 检查 `events/stderr.tail` 是否含标记行。
- [其它 NPB 版本补丁失败] → 注释钉死 NPB 3.4.3；测试对保存的循环片段打补丁。
- [WSL CI 没有 mpif90] → 测试不要求编译 CG。

## 迁移

部署 sidecar 到 `/shared/agent-sidecar`。在 mn 上设置 `NPB_MPI_ROOT` 指向 NPB 3.4-MPI 树，运行 `scripts/demo_npb_cg_segfault.sh`。回滚：删除 example 目录和 demo 脚本；未改动的 NPB 原树不受影响。

## 待决问题

无。
