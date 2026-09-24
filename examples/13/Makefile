# 13 — 总表 13 cgroup 内存超限。复用 02 的 cgroup_oom，避免第二套 malloc。
# 本集群不强制内存 cgroup（CR_Core + proctrack/linuxproc，无 cgroup.conf），
# --mem=16M 能分配，但 256MiB malloc 仍 exit 0，主码 ok，断言 slurm_oom 不成立。
.PHONY: all clean

all:
	$(MAKE) -C ../02

clean:
	$(MAKE) -C ../02 clean
