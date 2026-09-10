/* MPI segfault fault fixture for agent-sidecar analysis demos.
 * Usage: mpi_fault_segfault [work_s] [fault_rank]
 * Default: work 10s, segfault on rank 0.
 * All ranks work first so proc-monitor can sample (pid_count > 0).
 */
#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    MPI_Init(&argc, &argv);
    int rank = 0, nrank = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &nrank);

    int work_s = 10;
    int fault_rank = 0;
    if (argc > 1 && argv[1][0] != '\0') {
        work_s = atoi(argv[1]);
        if (work_s < 1) {
            work_s = 1;
        }
    }
    if (argc > 2 && argv[2][0] != '\0') {
        fault_rank = atoi(argv[2]);
    }

    time_t t0 = time(NULL);
    volatile unsigned long busy = 0;
    while ((time(NULL) - t0) < work_s) {
        for (int i = 0; i < 100000; i++) {
            busy += (unsigned long)i;
        }
        if (rank == 0) {
            fprintf(stderr, "mpi_fault_segfault rank0 working elapsed=%ld busy=%lu\n",
                    (long)(time(NULL) - t0), (unsigned long)busy);
            fflush(stderr);
        }
        usleep(200000);
    }

    MPI_Barrier(MPI_COMM_WORLD);
    if (rank == fault_rank) {
        fprintf(stderr, "rank %d segfault (null deref)\n", rank);
        fflush(stderr);
        *(volatile int *)0 = 1;
    }
    MPI_Finalize();
    return 0;
}
