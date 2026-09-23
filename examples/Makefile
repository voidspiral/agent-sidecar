# Case library: one dir per 调研2 总表 ID (2a+2b → 02).
# Incomplete cases have a no-op `all`. Health mpi_io_load stays at this directory.
CC ?= mpicc
CFLAGS ?= -O2 -Wall -Wextra
CASES := 01 02 03 04 05 06 06x 07a 07b 08 09 10 11a 11b 12 13 14 15 16 17 18 19 20 21 22 23

.PHONY: all clean $(CASES)

all: $(CASES) mpi_io_load

$(CASES):
	$(MAKE) -C $@

mpi_io_load: mpi_io_load.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	@for d in $(CASES); do $(MAKE) -C $$d clean; done
	rm -f mpi_io_load mpi-io.rank*.bin
