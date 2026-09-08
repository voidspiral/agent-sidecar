/* MPI ranks: IO-dense write/read/fsync, then an optional CPU-dense burn.
 * Usage: mpi_io_load [io_seconds] [work_dir] [cpu_seconds]
 * Default: 60 seconds IO, work_dir=., 30 seconds CPU.
 * cpu_seconds 0 skips the CPU phase.
 * On this cluster put work_dir on NFS, e.g. /shared/mpi-io.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static void cpu_burn(int seconds, char *buf, size_t chunk)
{
    struct timespec t0, now;
    volatile unsigned long acc = 1ul;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (;;) {
#if defined(__GNUC__)
        __asm__ __volatile__("" ::: "memory");
#endif
        clock_gettime(CLOCK_MONOTONIC, &now);
        if ((now.tv_sec - t0.tv_sec) >= seconds) {
            break;
        }
        for (size_t i = 0; i < chunk; i++) {
            unsigned char c = (unsigned char)buf[i];
            acc += c + (unsigned long)i;
            buf[i] = (char)(acc ^ (unsigned long)i);
        }
    }
}

int main(int argc, char **argv)
{
    MPI_Init(&argc, &argv);
    int rank = 0, nrank = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &nrank);

    int io_seconds = 60;
    int cpu_seconds = 30;
    const char *dir = ".";
    if (argc > 1 && argv[1][0] != '\0') {
        io_seconds = atoi(argv[1]);
        if (io_seconds <= 0) {
            io_seconds = 60;
        }
    }
    if (argc > 2 && argv[2][0] != '\0') {
        dir = argv[2];
    }
    if (argc > 3 && argv[3][0] != '\0') {
        cpu_seconds = atoi(argv[3]);
        if (cpu_seconds < 0) {
            cpu_seconds = 0;
        }
    }

    const size_t chunk = 1u << 20; /* 1 MiB */
    char *buf = malloc(chunk);
    if (buf == NULL) {
        fprintf(stderr, "rank %d: malloc failed\n", rank);
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
    memset(buf, (unsigned char)(rank + 1), chunk);

    char path[512];
    int nw = snprintf(path, sizeof path, "%s/mpi-io.rank%d.bin", dir, rank);
    if (nw < 0 || (size_t)nw >= sizeof path) {
        fprintf(stderr, "rank %d: path too long\n", rank);
        MPI_Abort(MPI_COMM_WORLD, 2);
    }

    int fd = open(path, O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) {
        fprintf(stderr, "rank %d: open %s: %s\n", rank, path, strerror(errno));
        MPI_Abort(MPI_COMM_WORLD, 3);
    }

    time_t t0 = time(NULL);
    unsigned long ops = 0;
    while ((time(NULL) - t0) < io_seconds) {
        if (lseek(fd, 0, SEEK_SET) < 0) {
            break;
        }
        ssize_t w = write(fd, buf, chunk);
        if (w < 0) {
            fprintf(stderr, "rank %d: write: %s\n", rank, strerror(errno));
            break;
        }
        (void)fsync(fd);
        if (lseek(fd, 0, SEEK_SET) < 0) {
            break;
        }
        ssize_t r = read(fd, buf, chunk);
        (void)r;
        ops++;
        if (rank == 0 && (ops % 32ul) == 0ul) {
            fprintf(stderr, "mpi_io_load rank0 ops=%lu elapsed=%ld\n",
                    ops, (long)(time(NULL) - t0));
        }
    }

    close(fd);
    (void)unlink(path);
    MPI_Barrier(MPI_COMM_WORLD);
    if (rank == 0) {
        fprintf(stderr, "mpi_io_load io_phase done ranks=%d io_seconds=%d ops_rank0=%lu\n",
                nrank, io_seconds, ops);
    }

    if (cpu_seconds <= 0) {
        /* skip CPU phase */
    } else {
        MPI_Barrier(MPI_COMM_WORLD);
        if (rank == 0) {
            fprintf(stderr, "mpi_io_load cpu_phase start seconds=%d\n", cpu_seconds);
        }
        time_t cpu_t0 = time(NULL);
        cpu_burn(cpu_seconds, buf, chunk);
        MPI_Barrier(MPI_COMM_WORLD);
        if (rank == 0) {
            fprintf(stderr, "mpi_io_load cpu_phase done elapsed=%ld\n",
                    (long)(time(NULL) - cpu_t0));
        }
    }

    if (rank == 0) {
        fprintf(stderr, "mpi_io_load done ranks=%d io_seconds=%d cpu_seconds=%d ops_rank0=%lu\n",
                nrank, io_seconds, cpu_seconds, ops);
    }
    free(buf);
    MPI_Finalize();
    return 0;
}
