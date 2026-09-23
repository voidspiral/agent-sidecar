# 06x — 总表 6x MPI_Abort（已完成）
CC ?= mpicc
CFLAGS ?= -O2 -Wall -Wextra

.PHONY: all clean

all: mpi_fault_abort

mpi_fault_abort: mpi_fault_abort.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f mpi_fault_abort
