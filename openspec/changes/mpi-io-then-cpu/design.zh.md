## 背景

`examples/mpi_io_load.c` 是本集群 `agent srun` 的 NFS 正常路径演示。每个 rank
对 `work_dir` 下 1 MiB 文件做 write/fsync/read。mpi-monitor 记的是
`/proc/<pid>/io` 的 `write_bytes`（块层）以及 `utime+stime` 的进程 CPU。IO
循环里进程堵在 NFS `fsync`，overlay 上 CPU 在 MPI 启动尖峰后大约只有 5%。
这是正确记账，但演示看不到 CPU 密集段。

约束：二进制名仍为 `mpi_io_load`（supervisor `--match`）；Python 3.10+
unittest；不用 ClusterHelm；不改采集字段。

## 目标 / 非目标

**目标：** 在现有 IO 循环之后，按可配置时长做本地 CPU burn；先 close/unlink；
barrier；rank0 打日志；argv 保持兼容。

**非目标：** 把 `read_bytes` 改成 `rchar`；burn 循环里做 MPI 集合通信；再做一个
示例二进制；改 live-plot 或 job-assist。

## 决策

### 1. 同一二进制，第三参数为 CPU 秒数

保持 `mpi_io_load [io_seconds] [work_dir] [cpu_seconds]`。默认：60、`.`、30。
`cpu_seconds == 0` 跳过 CPU 阶段，便于只测 IO。不要把 `cpu_seconds` 插成
argv2（会破坏 `work_dir`）。

### 2. CPU 前先 close/unlink，再 `MPI_Barrier`

IO 阶段结束本来就会 close/unlink。CPU 只用内存里那块 1 MiB 缓冲（volatile
校验/改写），避免 `-O2` 删掉循环，且 `write_bytes` 保持平坦。unlink 后
barrier，各 rank 一起进入 burn。

### 3. CPU burn 是本地紧循环，不是 MPI 计算

内循环不做 `MPI_Allreduce`（两节点单核测试机会变成等待）。Rank 0 打
`cpu_phase start` / `cpu_phase done`。IO 阶段 `ops % 32` 进度日志保留。

### 4. 测试：源码契约必跑；有 mpicc 再编译运行

unittest 解析 `examples/mpi_io_load.c`：argv3、unlink 先于 CPU、阶段日志字符串。
若 PATH 上有 `mpicc` 和 `mpirun`/`mpiexec`，编到临时目录，跑 `1s IO + 1s CPU`，
断言 stderr 标记且退出码 0。集群 `salloc` 属于运维验证，不是 CI。

## 风险 / 权衡

- 常用命令 `mpi_io_load 60 /shared/mpi-io` 墙钟从 60s 变成约 90s。演示 overlay
  可以接受；argv3 传 `0` 则仍是 60s 纯 IO。
- CPU 循环大约占满 1 核，不是多核扩展。符合本集群计算节点 1 vCPU。

## 迁移

在 NFS 上重编（`make -C examples` 或 `mpicc` 写到 `/shared`）。原两参数命令
仍可用，并多一段 30s CPU。演示脚本可传 `AGENT_MPI_CPU_SECONDS`（默认 30）。
