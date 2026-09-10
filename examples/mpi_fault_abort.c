/* MPI abort fault fixture for agent-sidecar analysis demos.
 * Usage: mpi_fault_abort [work_s] [abort_rank] [errorcode]
 * Default: work 10s, abort on rank 0 with errorcode 1.
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
    int abort_rank = 0;
    int errorcode = 1;
    if (argc > 1 && argv[1][0] != '\0') {
        work_s = atoi(argv[1]);
        if (work_s < 1) {
            work_s = 1;
        }
    }
    if (argc > 2 && argv[2][0] != '\0') {
        abort_rank = atoi(argv[2]);
    }
    if (argc > 3 && argv[3][0] != '\0') {
        errorcode = atoi(argv[3]);
        if (errorcode == 0) {
            errorcode = 1;
        }
    }

    time_t t0 = time(NULL);
    volatile unsigned long busy = 0;
    while ((time(NULL) - t0) < work_s) {
        for (int i = 0; i < 100000; i++) {
            busy += (unsigned long)i;
        }
        if (rank == 0) {
            fprintf(stderr, "mpi_fault_abort rank0 working elapsed=%ld busy=%lu\n",
                    (long)(time(NULL) - t0), (unsigned long)busy);
            fflush(stderr);
        }
        usleep(200000);
    }

    MPI_Barrier(MPI_COMM_WORLD);
    if (rank == abort_rank) {
        fprintf(stderr,
                "rank %d called MPI_Abort(comm=MPI_COMM_WORLD, errorcode=%d)\n",
                rank, errorcode);
        fflush(stderr);
        MPI_Abort(MPI_COMM_WORLD, errorcode);
    }
    MPI_Finalize();
    return 0;
}
