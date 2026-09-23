# 05 — 总表 5 SIGFPE（已完成），期望 reason_code=mpi_fpe
CC ?= mpicc
CFLAGS ?= -O2 -Wall -Wextra

.PHONY: all clean

all: mpi_fault_fpe

mpi_fault_fpe: mpi_fault_fpe.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f mpi_fault_fpe
