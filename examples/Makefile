CC ?= mpicc
CFLAGS ?= -O2 -Wall -Wextra
BIN = mpi_io_load

.PHONY: all clean

all: $(BIN)

$(BIN): mpi_io_load.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(BIN) mpi-io.rank*.bin
