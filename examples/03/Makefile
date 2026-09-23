# 03 — 总表 3 段错误（已完成）
# 子目标：mpi_fault_segfault（默认）；npb 需 NPB_MPI_ROOT，不纳入 all
CC ?= mpicc
CFLAGS ?= -O2 -Wall -Wextra

.PHONY: all clean npb

all: mpi_fault_segfault

mpi_fault_segfault: mpi_fault_segfault.c
	$(CC) $(CFLAGS) -o $@ $<

npb:
	bash npb_cg_mid_segfault/build.sh

clean:
	rm -f mpi_fault_segfault cg.*.x
