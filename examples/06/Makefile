# 06 — 总表 6 MPI 死锁（已完成），期望 mpi_deadlock；demo 必须带 --time
CC ?= mpicc
CFLAGS ?= -O2 -Wall -Wextra

.PHONY: all clean

all: mpi_fault_deadlock

mpi_fault_deadlock: mpi_fault_deadlock.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f mpi_fault_deadlock
