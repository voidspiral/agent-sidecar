# 07a — 总表 7a 应用 I/O ENOENT（已完成），期望 execution_error
CC ?= mpicc
CFLAGS ?= -O2 -Wall -Wextra

.PHONY: all clean

all: io_enoent

io_enoent: io_enoent.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f io_enoent
