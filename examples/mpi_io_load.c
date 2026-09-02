/* MPI ranks generate ~60s of local write/read/fsync load.
 * Usage: mpi_io_load [seconds] [work_dir]
 * Default: 60 seconds, work_dir=.
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

int main(int argc, char **argv)
{
    MPI_Init(&argc, &argv);
    int rank = 0, nrank = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &nrank);

    int seconds = 60;
    const char *dir = ".";
    if (argc > 1 && argv[1][0] != '\0') {
        seconds = atoi(argv[1]);
        if (seconds <= 0) {
            seconds = 60;
        }
    }
    if (argc > 2 && argv[2][0] != '\0') {
        dir = argv[2];
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
    while ((time(NULL) - t0) < seconds) {
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
        if ((ops % 8ul) == 0ul) {
            MPI_Barrier(MPI_COMM_WORLD);
        }
    }

    close(fd);
    (void)unlink(path);
    MPI_Barrier(MPI_COMM_WORLD);
    if (rank == 0) {
        fprintf(stderr, "mpi_io_load done ranks=%d seconds=%d ops_rank0=%lu\n",
                nrank, seconds, ops);
    }
    free(buf);
    MPI_Finalize();
    return 0;
}
