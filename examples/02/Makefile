# 02 — 总表 2a 内核 OOM（仅 unittest 注入）+ 2b Slurm cgroup OOM（本二进制）
# 2a：禁止 srun demo 撑满节点；见 tests/test_node_diag.py killed process → node_local
# 2b/13：cgroup_oom + 很小 --mem，期望 slurm_oom
CC ?= mpicc
CFLAGS ?= -O2 -Wall -Wextra

.PHONY: all clean

all: cgroup_oom

cgroup_oom: cgroup_oom.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f cgroup_oom
