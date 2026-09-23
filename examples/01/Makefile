# 01 — 总表 1 缺动态库（已完成）
# 把 libmissing.so 编到 missing-so-build/，可执行文件 -Wl,-rpath 指向
# 从不部署该库的 not-deployed-lib/。stderr 期望 cannot open shared object。
CC ?= mpicc
CFLAGS ?= -O2 -Wall -Wextra
RPATH_DIR := not-deployed-lib
SO_DIR := missing-so-build

.PHONY: all clean

all: mpi_missing_so

$(SO_DIR)/libmissing.so: missing.c
	mkdir -p $(SO_DIR)
	$(CC) $(CFLAGS) -shared -fPIC -o $@ $<

mpi_missing_so: mpi_missing_so.c $(SO_DIR)/libmissing.so
	mkdir -p $(RPATH_DIR)
	rm -f $(RPATH_DIR)/libmissing.so
	$(CC) $(CFLAGS) -o $@ mpi_missing_so.c -L$(SO_DIR) -lmissing -Wl,-rpath,$(CURDIR)/$(RPATH_DIR)

clean:
	rm -f mpi_missing_so
	rm -rf $(SO_DIR) $(RPATH_DIR)
