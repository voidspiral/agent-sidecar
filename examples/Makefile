CC ?= mpicc
CFLAGS ?= -O2 -Wall -Wextra
BIN = mpi_io_load mpi_fault_abort mpi_fault_segfault
# NPB CG mid-segfault: bash npb_cg_mid_segfault/build.sh (needs NPB_MPI_ROOT)

.PHONY: all clean

all: $(BIN)

mpi_io_load: mpi_io_load.c
	$(CC) $(CFLAGS) -o $@ $<

mpi_fault_abort: mpi_fault_abort.c
	$(CC) $(CFLAGS) -o $@ $<

mpi_fault_segfault: mpi_fault_segfault.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(BIN) mpi-io.rank*.bin
